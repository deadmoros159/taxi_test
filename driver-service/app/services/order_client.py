"""
Клиент order-service для получения сводки водителя (рейтинг, баланс, задолженность).
"""
import sys
import os
import logging
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../shared'))

from http_client import ResilientHTTPClient
from correlation import get_correlation_id
from app.core.config import settings

logger = logging.getLogger(__name__)


class OrderServiceClient:
    def __init__(self):
        self.client = ResilientHTTPClient(
            base_url=settings.ORDER_SERVICE_URL,
            timeout=5.0,
        )

    async def get_driver_summary(
        self, driver_user_id: int, token: str
    ) -> Optional[Dict[str, Any]]:
        """
        Сводка по водителю: рейтинг, balance (долг), debt_info (просрочка/блокировка).
        driver_user_id — user_id водителя в auth (в order-service это driver_id в заказах).
        """
        try:
            correlation_id = get_correlation_id()
            headers = {"Authorization": f"Bearer {token}"}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            response = await self.client.get(
                f"/api/v1/drivers/{driver_user_id}/summary",
                headers=headers,
            )

            if response.status_code == 200:
                return response.json()
            logger.warning(
                f"Order service summary failed: {response.status_code} for driver_user_id={driver_user_id}"
            )
            return None
        except Exception as e:
            logger.error(f"Error fetching driver summary from order-service: {e}", exc_info=True)
            return None

    async def close(self):
        await self.client.close()


order_client = OrderServiceClient()
