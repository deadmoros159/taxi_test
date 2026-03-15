"""Сервис отправки уведомлений о статусе заказа в Telegram."""

import logging
import httpx

from app.core.config import settings
from app.models.order import Order

logger = logging.getLogger(__name__)


async def notify_telegram_order_status(order: Order) -> None:
    """
    Уведомить пассажира в Telegram о смене статуса заказа.
    Вызывает auth-service (telegram_user_id) и telegram-bot-service (отправка).
    """
    if not settings.TELEGRAM_BOT_SERVICE_URL or not settings.AUTH_INTERNAL_KEY:
        logger.debug("Telegram notifications disabled (TELEGRAM_BOT_SERVICE_URL or AUTH_INTERNAL_KEY not set)")
        return

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/internal/users/{order.passenger_id}/telegram-id",
                headers={"X-Internal-Key": settings.AUTH_INTERNAL_KEY},
            )
            if resp.status_code != 200:
                logger.warning(f"Auth internal API returned {resp.status_code}")
                return
            data = resp.json()
            telegram_user_id = data.get("telegram_user_id")
            if telegram_user_id is None:
                return

            notify_resp = await client.post(
                f"{settings.TELEGRAM_BOT_SERVICE_URL}/api/v1/telegram/notify-order-status",
                json={
                    "telegram_user_id": telegram_user_id,
                    "order_id": order.id,
                    "status": order.status.value,
                },
            )
            if notify_resp.status_code != 200:
                logger.warning(f"Telegram notify returned {notify_resp.status_code}: {notify_resp.text}")
        except httpx.RequestError as e:
            logger.warning(f"Telegram notify request failed: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error in telegram notify: {e}")
