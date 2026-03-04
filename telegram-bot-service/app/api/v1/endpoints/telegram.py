from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from app.services.auth_client import AuthClient

router = APIRouter()


class TelegramIdAuthRequest(BaseModel):
    telegram_user_id: int = Field(..., description="ID пользователя в Telegram")


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


