from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from typing import Optional, List
from app.models.order import Order, OrderStatus
from app.schemas.order import OrderCreate
import logging

logger = logging.getLogger(__name__)


class OrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_order(
        self, 
        order_data: OrderCreate, 
        passenger_id: int,
        estimated_price: Optional[float] = None
    ) -> Order:
        from datetime import datetime, timezone
        order_date = order_data.order_date if order_data.order_date else datetime.now(timezone.utc)
        
        order = Order(
            passenger_id=passenger_id,
            start_latitude=order_data.start_latitude,
            start_longitude=order_data.start_longitude,
            start_address=order_data.start_address,
            end_latitude=order_data.end_latitude,
            end_longitude=order_data.end_longitude,
            end_address=order_data.end_address,
            status=OrderStatus.PENDING,
            order_date=order_date,
            price=estimated_price,
        )
        
        self.db.add(order)
        await self.db.commit()
        await self.db.refresh(order)
        
        return order

    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_active_orders_for_drivers(self) -> List[Order]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Order)
            .where(
                Order.status == OrderStatus.PENDING,
                (Order.order_date.is_(None)) | (Order.order_date <= now),
            )
            .order_by(Order.order_date.desc().nullslast(), Order.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_scheduled_orders_for_drivers(self) -> List[Order]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Order)
            .where(
                Order.status == OrderStatus.PENDING,
                Order.order_date.is_not(None),
                Order.order_date > now,
            )
            .order_by(Order.order_date.asc())
        )
        return list(result.scalars().all())

    async def get_orders_by_passenger(self, passenger_id: int, limit: int = 50) -> List[Order]:
        result = await self.db.execute(
            select(Order).where(Order.passenger_id == passenger_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_orders_by_driver(self, driver_id: int, limit: int = 50) -> List[Order]:
        result = await self.db.execute(
            select(Order).where(Order.driver_id == driver_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all_orders(self, limit: int = 100, status: Optional[OrderStatus] = None) -> List[Order]:
        stmt = select(Order)
        if status:
            stmt = stmt.where(Order.status == status)
        stmt = stmt.order_by(Order.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def accept_order(
        self,
        order_id: int,
        driver_id: int,
        driver_lat: float,
        driver_lng: float,
        estimated_time: int,
        vehicle_info: str
    ) -> Optional[Order]:
        from datetime import datetime
        
        order = await self.get_order_by_id(order_id)
        if not order or order.status != OrderStatus.PENDING:
            return None

        order.driver_id = driver_id
        order.status = OrderStatus.ACCEPTED
        order.driver_location_lat = driver_lat
        order.driver_location_lng = driver_lng
        order.estimated_time_minutes = estimated_time
        order.vehicle_info = vehicle_info
        order.accepted_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def update_order_status(
        self,
        order_id: int,
        status: OrderStatus,
        **kwargs
    ) -> Optional[Order]:
        from datetime import datetime
        
        order = await self.get_order_by_id(order_id)
        if not order:
            return None

        order.status = status
        
        if status == OrderStatus.COMPLETED:
            order.completed_at = datetime.utcnow()
        elif status in [OrderStatus.CANCELLED, OrderStatus.CANCELLED_BY_DRIVER, OrderStatus.CANCELLED_BY_PASSENGER]:
            order.cancelled_at = datetime.utcnow()
            if "cancellation_reason" in kwargs:
                order.cancellation_reason = kwargs["cancellation_reason"]
            if "cancelled_by" in kwargs:
                order.cancelled_by = kwargs["cancelled_by"]

        for key, value in kwargs.items():
            if hasattr(order, key) and key not in ["cancellation_reason", "cancelled_by"]:
                setattr(order, key, value)

        await self.db.commit()
        await self.db.refresh(order)
        return order
    
    async def update_driver_location(
        self,
        order_id: int,
        latitude: float,
        longitude: float,
        route_history: Optional[str] = None
    ) -> Optional[Order]:
        order = await self.get_order_by_id(order_id)
        if not order:
            return None
        
        order.driver_location_lat = latitude
        order.driver_location_lng = longitude
        if route_history:
            order.route_history = route_history
        
        await self.db.commit()
        await self.db.refresh(order)
        return order

    async def cancel_order(
        self,
        order_id: int,
        reason: str,
        cancelled_by: int,
        is_driver: bool = False
    ) -> Optional[Order]:
        status = OrderStatus.CANCELLED_BY_DRIVER if is_driver else OrderStatus.CANCELLED_BY_PASSENGER
        return await self.update_order_status(
            order_id,
            status,
            cancellation_reason=reason,
            cancelled_by=cancelled_by
        )

