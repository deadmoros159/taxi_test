"""
Сервис для расчета статистики
"""
import httpx
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from app.core.config import settings
from app.services.aggregation_service import AggregationService

logger = logging.getLogger(__name__)


class StatsService:
    """Сервис для расчета статистики"""
    
    def __init__(self):
        self.aggregation = AggregationService()
        self.order_url = settings.ORDER_SERVICE_URL
        self.driver_url = settings.DRIVER_SERVICE_URL
        self.auth_url = settings.AUTH_SERVICE_URL

    async def get_dashboard_stats(self, token: str) -> Dict:
        """Получить статистику для дашборда"""
        try:
            # Получаем данные параллельно
            drivers = await self.aggregation.get_all_drivers(token)
            orders = await self.aggregation.get_all_orders(token)
            
            # Подсчитываем статистику
            total_drivers = len(drivers)
            active_drivers = len([d for d in drivers if d.get("status") == "active"])
            
            total_orders = len(orders)
            pending_orders = len([o for o in orders if o.get("status") == "pending"])
            completed_orders = len([o for o in orders if o.get("status") == "completed"])
            
            # Рассчитываем за сегодня
            today = datetime.utcnow().date()
            today_orders = [
                o for o in orders
                if o.get("created_at") and 
                datetime.fromisoformat(o["created_at"].replace("Z", "+00:00")).date() == today
            ]
            
            return {
                "drivers": {
                    "total": total_drivers,
                    "active": active_drivers,
                    "pending": total_drivers - active_drivers
                },
                "orders": {
                    "total": total_orders,
                    "pending": pending_orders,
                    "completed": completed_orders,
                    "today": len(today_orders)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error calculating dashboard stats: {e}")
            return {
                "drivers": {"total": 0, "active": 0, "pending": 0},
                "orders": {"total": 0, "pending": 0, "completed": 0, "today": 0},
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_orders_stats(
        self,
        token: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """Получить статистику по заказам за период"""
        try:
            orders = await self.aggregation.get_all_orders(token)
            
            if start_date or end_date:
                filtered_orders = []
                for order in orders:
                    if not order.get("created_at"):
                        continue
                    order_date = datetime.fromisoformat(
                        order["created_at"].replace("Z", "+00:00")
                    )
                    if start_date and order_date < start_date:
                        continue
                    if end_date and order_date > end_date:
                        continue
                    filtered_orders.append(order)
                orders = filtered_orders
            
            # Группируем по статусам
            status_counts = {}
            total_revenue = 0.0
            
            for order in orders:
                status = order.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
                
                if order.get("price"):
                    total_revenue += float(order["price"])
            
            return {
                "total": len(orders),
                "by_status": status_counts,
                "total_revenue": total_revenue,
                "average_order_value": total_revenue / len(orders) if orders else 0,
                "period": {
                    "start": start_date.isoformat() if start_date else None,
                    "end": end_date.isoformat() if end_date else None
                }
            }
        except Exception as e:
            logger.error(f"Error calculating orders stats: {e}")
            return {
                "total": 0,
                "by_status": {},
                "total_revenue": 0.0,
                "average_order_value": 0.0
            }

    async def get_drivers_stats(self, token: str) -> Dict:
        """Получить статистику по водителям"""
        try:
            drivers = await self.aggregation.get_all_drivers(token)
            
            # Группируем по статусам
            status_counts = {}
            verified_count = 0
            
            for driver in drivers:
                status = driver.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
                
                if driver.get("is_verified"):
                    verified_count += 1
            
            return {
                "total": len(drivers),
                "by_status": status_counts,
                "verified": verified_count,
                "not_verified": len(drivers) - verified_count
            }
        except Exception as e:
            logger.error(f"Error calculating drivers stats: {e}")
            return {
                "total": 0,
                "by_status": {},
                "verified": 0,
                "not_verified": 0
            }

