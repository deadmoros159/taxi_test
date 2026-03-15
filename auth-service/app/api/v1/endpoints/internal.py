"""Внутренние эндпоинты для межсервисного взаимодействия (order-service и др.)."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter()


async def verify_internal_key(x_internal_key: str | None = Header(None, alias="X-Internal-Key")) -> None:
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=503, detail="Internal API not configured")
    if x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")


@router.get("/users/{user_id}/telegram-id")
async def get_telegram_id_by_user_id(
    user_id: int,
    _: None = Depends(verify_internal_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить telegram_user_id по user_id.
    Используется order-service для отправки уведомлений в Telegram.
    """
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user or user.telegram_user_id is None:
        return {"telegram_user_id": None}
    return {"telegram_user_id": user.telegram_user_id}
