"""
API endpoints для авторизации через Telegram
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
import logging

from app.services.auth_client import AuthClient

logger = logging.getLogger(__name__)

router = APIRouter()


class TelegramAuthRequest(BaseModel):
    """Запрос на авторизацию через Telegram"""
    phone_number: str = Field(..., description="Номер телефона в формате +998XXXXXXXXX")
    full_name: str = Field(..., description="Полное имя пользователя")
    telegram_user_id: int = Field(..., description="ID пользователя в Telegram")
    telegram_username: Optional[str] = Field(None, description="Username пользователя в Telegram")


class TelegramAuthResponse(BaseModel):
    """Ответ с токенами после авторизации"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Тип токена")
    expires_in: int = Field(..., description="Время жизни access токена в секундах")
    user_id: int = Field(..., description="ID пользователя")
    full_name: Optional[str] = Field(None, description="Полное имя пользователя")
    phone_number: Optional[str] = Field(None, description="Номер телефона пользователя")


@router.post("/authorize", response_model=TelegramAuthResponse)
async def authorize_via_telegram(request: TelegramAuthRequest):
    """
    Авторизация через Telegram (API endpoint).
    
    Принимает данные пользователя из Telegram и возвращает JWT токены.
    Используется клиентскими приложениями для получения токенов.
    """
    auth_client = AuthClient()
    try:
        result = await auth_client.authorize_via_telegram(
            phone_number=request.phone_number,
            full_name=request.full_name,
            telegram_user_id=request.telegram_user_id,
            telegram_username=request.telegram_username
        )

        if result:
            return TelegramAuthResponse(
                access_token=result.get("access_token"),
                refresh_token=result.get("refresh_token"),
                token_type="bearer",
                expires_in=result.get("expires_in", 3600),  # 1 час по умолчанию
                user_id=result.get("user_id"),
                full_name=result.get("full_name"),
                phone_number=result.get("phone_number")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to authorize via Telegram"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in authorize_via_telegram API: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authorization"
        )
    finally:
        await auth_client.close()

