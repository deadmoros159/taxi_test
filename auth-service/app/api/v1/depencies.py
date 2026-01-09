# app/api/v1/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.token_service import token_service

security = HTTPBearer()


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Зависимость для получения текущего пользователя из токена"""
    token = credentials.credentials

    # Извлекаем токен из заголовка
    token_data = token_service.verify_access_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def get_current_user_id(
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int:
    """Зависимость для получения только ID пользователя"""
    token_data = await get_current_user(credentials)
    return token_data["user_id"]