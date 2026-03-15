import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.services.auth_client import AuthClient
from app.lang_store import get_user_lang
from app.i18n.translations import get_text, DEFAULT_LANG

logger = logging.getLogger(__name__)

router = APIRouter()


class TelegramIdAuthRequest(BaseModel):
    telegram_user_id: int = Field(..., description="ID пользователя в Telegram")


class NotifyOrderStatusRequest(BaseModel):
    """Запрос на уведомление о смене статуса заказа"""
    telegram_user_id: int = Field(..., description="ID пользователя в Telegram")
    order_id: int = Field(..., description="ID заказа")
    status: str = Field(..., description="Статус заказа (pending, accepted, driver_arrived, in_progress, completed, cancelled, cancelled_by_driver, cancelled_by_passenger)")


@router.get("/check/{telegram_user_id}")
async def check_telegram_user(telegram_user_id: int):
    client = AuthClient()
    try:
        result = await client.telegram_user_exists(telegram_user_id)
        if result is None:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="auth-service unavailable")
        return result
    finally:
        await client.close()


@router.post("/authorize-by-id")
async def authorize_by_id(payload: TelegramIdAuthRequest):
    client = AuthClient()
    try:
        result = await client.authorize_via_telegram_id(payload.telegram_user_id)
        if not result:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram user not found")
        return result
    finally:
        await client.close()


@router.post("/notify-order-status")
async def notify_order_status(payload: NotifyOrderStatusRequest):
    """
    Отправить пользователю уведомление о смене статуса заказа.
    Вызывается order-service при изменении статуса.
    """
    from app.main import bot as global_bot

    if not global_bot:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot not initialized")

    status_key = f"order_status_{payload.status}"
    lang = get_user_lang(payload.telegram_user_id)
    text = get_text(status_key, lang, order_id=payload.order_id)
    if text == status_key:  # ключ не найден
        text = get_text("order_status_pending", lang, order_id=payload.order_id)

    try:
        await global_bot.send_message(
            chat_id=payload.telegram_user_id,
            text=text,
            parse_mode="HTML",
        )
        return {"ok": True}
    except Exception as e:
        logger.warning(f"Failed to send order status to {payload.telegram_user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send notification")


