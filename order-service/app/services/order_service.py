from typing import Optional
from datetime import datetime, timedelta
import logging
import sys
import os

# Добавляем shared в путь для импорта геолокации
shared_path = os.path.join(os.path.dirname(__file__), '../../../../shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

try:
    from shared.geolocation import calculate_distance, estimate_travel_time
except ImportError:
    # Fallback если shared не доступен
    import math
    def calculate_distance(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    
    def estimate_travel_time(distance_km, avg_speed_kmh=40):
        if distance_km <= 0:
            return 0
        return max(1, int((distance_km / avg_speed_kmh) * 60))

from app.repositories.order_repository import OrderRepository
from app.repositories.driver_debt_repository import DriverDebtRepository
from app.models.order import Order, OrderStatus
from app.schemas.order import OrderCreate, OrderAccept, OrderCompleteData
from app.services.pricing_service import calculate_price, calculate_estimated_price, calculate_distance
from app.core.config import settings

logger = logging.getLogger(__name__)


class OrderService:
    def __init__(
        self,
        order_repo: OrderRepository,
        debt_repo: DriverDebtRepository
    ):
        self.order_repo = order_repo
        self.debt_repo = debt_repo

    async def create_order(self, order_data: OrderCreate, passenger_id: int) -> Order:
        """Создать новый заказ с расчетом предварительной цены"""
        # Рассчитываем предварительную цену (OSRM или haversine)
        estimated_price, estimated_distance = await calculate_estimated_price(
            order_data.start_latitude,
            order_data.start_longitude,
            order_data.end_latitude,
            order_data.end_longitude
        )
        
        order = await self.order_repo.create_order(order_data, passenger_id, estimated_price)
        logger.info(f"Order {order.id} created by passenger {passenger_id} with estimated price {estimated_price}")
        return order

    async def accept_order(
        self,
        order_id: int,
        driver_id: int,
        accept_data: OrderAccept,
        vehicle_info: str
    ) -> Optional[Order]:
        """Принять заказ водителем"""
        order = await self.order_repo.get_order_by_id(order_id)
        if not order:
            return None

        # Проверяем, не заблокирован ли водитель
        unpaid_debts = await self.debt_repo.get_unpaid_debts(driver_id=driver_id)
        blocked_debts = [d for d in unpaid_debts if d.is_blocked]
        if blocked_debts:
            logger.warning(f"Driver {driver_id} is blocked due to unpaid debts")
            return None

        # Рассчитываем время до клиента
        distance = calculate_distance(
            accept_data.driver_location_lat,
            accept_data.driver_location_lng,
            order.start_latitude,
            order.start_longitude
        )
        estimated_time = estimate_travel_time(distance)

        # Принимаем заказ
        order = await self.order_repo.accept_order(
            order_id=order_id,
            driver_id=driver_id,
            driver_lat=accept_data.driver_location_lat,
            driver_lng=accept_data.driver_location_lng,
            estimated_time=estimated_time,
            vehicle_info=vehicle_info
        )

        if order:
            logger.info(f"Order {order_id} accepted by driver {driver_id}")
            # Создаем долг водителя (20% от заказа)
            if order.price:
                debt_amount = order.price * (settings.DRIVER_COMMISSION_PERCENT / 100)
                due_date = datetime.utcnow() + timedelta(days=settings.DEBT_CHECK_INTERVAL_DAYS)
                await self.debt_repo.create_debt(
                    type("DriverDebtCreate", (), {
                        "order_id": order.id,
                        "driver_id": driver_id,
                        "amount": debt_amount,
                        "due_date": due_date
                    })()
                )

        return order

    async def cancel_order(
        self,
        order_id: int,
        reason: str,
        user_id: int,
        is_driver: bool = False
    ) -> Optional[Order]:
        """Отменить заказ"""
        order = await self.order_repo.get_order_by_id(order_id)
        if not order:
            return None

        # Проверяем права на отмену
        if is_driver:
            if order.driver_id != user_id:
                return None
        else:
            if order.passenger_id != user_id:
                return None

        cancelled_order = await self.order_repo.cancel_order(
            order_id=order_id,
            reason=reason,
            cancelled_by=user_id,
            is_driver=is_driver
        )

        if cancelled_order:
            logger.info(f"Order {order_id} cancelled by {'driver' if is_driver else 'passenger'} {user_id}")

        return cancelled_order

    async def complete_order(
        self, 
        order_id: int, 
        driver_id: int,
        complete_data: Optional[OrderCompleteData] = None
    ) -> Optional[Order]:
        """Завершить заказ с расчетом финальной цены"""
        order = await self.order_repo.get_order_by_id(order_id)
        if not order or order.driver_id != driver_id:
            return None

        # Рассчитываем финальную цену на основе фактических данных
        actual_distance = None
        actual_time = None
        final_price = order.price  # Используем предварительную цену по умолчанию
        
        if complete_data:
            actual_distance = complete_data.actual_distance_km
            actual_time = complete_data.actual_time_minutes
            
            # Если есть фактические данные, рассчитываем финальную цену
            if actual_distance is not None:
                # Если есть фактическое время, используем его, иначе оцениваем
                if actual_time is None and order.accepted_at:
                    # Оцениваем время на основе времени между принятием и завершением
                    from datetime import datetime
                    time_diff = (datetime.utcnow() - order.accepted_at).total_seconds() / 60
                    actual_time = int(time_diff)
                
                final_price = calculate_price(actual_distance, actual_time)
        else:
            # Если фактических данных нет, рассчитываем на основе координат
            if order.end_latitude and order.end_longitude:
                actual_distance = calculate_distance(
                    order.start_latitude,
                    order.start_longitude,
                    order.end_latitude,
                    order.end_longitude
                )
                if order.accepted_at:
                    from datetime import datetime
                    time_diff = (datetime.utcnow() - order.accepted_at).total_seconds() / 60
                    actual_time = int(time_diff)
                    final_price = calculate_price(actual_distance, actual_time)

        # Обновляем заказ с финальной ценой и фактическими данными
        update_kwargs = {
            "price": final_price,
            "actual_distance_km": actual_distance,
            "actual_time_minutes": actual_time
        }
        
        if complete_data:
            if complete_data.end_latitude:
                update_kwargs["end_latitude"] = complete_data.end_latitude
            if complete_data.end_longitude:
                update_kwargs["end_longitude"] = complete_data.end_longitude
            if complete_data.end_address:
                update_kwargs["end_address"] = complete_data.end_address

        completed_order = await self.order_repo.update_order_status(
            order_id=order_id,
            status=OrderStatus.COMPLETED,
            **update_kwargs
        )

        if completed_order:
            logger.info(
                f"Order {order_id} completed by driver {driver_id} "
                f"with final price {final_price} (distance: {actual_distance} km, time: {actual_time} min)"
            )

        return completed_order

