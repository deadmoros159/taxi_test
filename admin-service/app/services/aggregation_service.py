"""
Сервис для агрегации данных из других микросервисов
"""
import httpx
import logging
from typing import Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class AggregationService:
    """Сервис для агрегации данных из разных микросервисов"""
    
    def __init__(self):
        self.auth_url = settings.AUTH_SERVICE_URL
        self.driver_url = settings.DRIVER_SERVICE_URL
        self.order_url = settings.ORDER_SERVICE_URL

    async def get_all_users(self, token: str) -> List[Dict]:
        """Получить всех пользователей"""
        async with httpx.AsyncClient() as client:
            try:
                # В реальности нужен эндпоинт для получения всех пользователей
                # Пока возвращаем пустой список
                return []
            except Exception as e:
                logger.error(f"Error fetching users: {e}")
                return []

    async def get_all_drivers(self, token: str) -> List[Dict]:
        """Получить всех водителей"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.driver_url}/api/v1/drivers",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
                return []
            except Exception as e:
                logger.error(f"Error fetching drivers: {e}")
                return []

    async def get_all_orders(
        self,
        token: str,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Получить все заказы"""
        async with httpx.AsyncClient() as client:
            try:
                # Нужно добавить эндпоинт в order-service для получения всех заказов
                # Пока используем существующий
                params = {}
                if status:
                    params["status"] = status
                if limit:
                    params["limit"] = limit
                
                # Временно возвращаем пустой список
                # TODO: Добавить эндпоинт GET /api/v1/orders/all в order-service
                return []
            except Exception as e:
                logger.error(f"Error fetching orders: {e}")
                return []

    async def get_driver_details(self, driver_id: int, token: str) -> Optional[Dict]:
        """Получить детальную информацию о водителе"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.driver_url}/api/v1/drivers/{driver_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
                return None
            except Exception as e:
                logger.error(f"Error fetching driver details: {e}")
                return None

    async def get_order_details(self, order_id: int, token: str) -> Optional[Dict]:
        """Получить детальную информацию о заказе"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.order_url}/api/v1/orders/{order_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json()
                return None
            except Exception as e:
                logger.error(f"Error fetching order details: {e}")
                return None


