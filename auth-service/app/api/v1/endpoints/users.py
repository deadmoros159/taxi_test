"""
Endpoints для управления пользователями и ролями
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import httpx
import logging

from app.core.database import get_db
from app.api.v1.dependencies import (
    get_current_user,
    require_admin,
    require_dispatcher,
    require_driver_management
)
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.models.role import UserRole
from app.schemas.auth import DispatcherRegisterRequest, StaffLoginRequest, TokensResponse
from app.utils.password import hash_password, verify_password
from app.services.token_service import token_service
from app.repositories.token_repository import TokenRepository
from app.utils.rate_limiter import rate_limiter
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
staff_router = APIRouter()
security = HTTPBearer()


class UpdateRoleRequest(BaseModel):
    """Запрос на изменение роли пользователя"""
    role: UserRole


class UserResponse(BaseModel):
    """Ответ с информацией о пользователе"""
    id: int
    full_name: str
    phone_number: str | None = None
    email: str | None = None
    role: str
    is_active: bool
    is_verified: bool
    
    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    """Расширенный ответ для личного кабинета (может включать данные водителя)"""
    id: int
    full_name: str
    phone_number: str | None = None
    email: str | None = None
    role: str
    is_active: bool
    is_verified: bool
    # Дополнительные данные для водителя (если роль = driver)
    driver_data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


@staff_router.post("/staff/dispatcher/register", response_model=UserResponse)
async def dispatcher_register(
    payload: DispatcherRegisterRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Регистрация (создание) диспетчера админом.
    """
    user_repo = UserRepository(db)
    existing = await user_repo.get_by_email(str(payload.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    try:
        password_hash = hash_password(payload.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    user = await user_repo.create_user(
        email=str(payload.email),
        full_name=payload.full_name,
        role=UserRole.DISPATCHER.value,
        is_active=True,
        is_verified=True,
        password_hash=password_hash,
    )

    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        phone_number=user.phone_number,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )


async def _staff_login_for_role(
    payload: StaffLoginRequest,
    role_required: str,
    db: AsyncSession,
) -> TokensResponse:
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(str(payload.email))
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.role != role_required:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User role is not allowed for this login (required: {role_required})",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    try:
        ok = verify_password(payload.password, user.password_hash)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tokens = token_service.create_tokens(
        user_id=user.id,
        full_name=user.full_name,
        role=user.role,
        email=user.email,
        phone_number=user.phone_number,
    )
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tokens",
        )

    access_token, refresh_token, refresh_token_id, expires_at = tokens
    token_repo = TokenRepository(db)
    await token_repo.create_refresh_token(
        user_id=user.id,
        token=refresh_token_id,
        expires_at=expires_at,
    )

    return TokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@staff_router.post("/staff/dispatcher/login", response_model=TokensResponse)
async def dispatcher_login(
    request: Request,
    payload: StaffLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Вход диспетчера по email/password (публичная)"""
    # rate limit (если Redis недоступен — в prod может упасть; в вашем rate_limiter он в prod строгий)
    await rate_limiter.check_request_limit(request, f"dispatcher_login:{payload.email}")
    return await _staff_login_for_role(payload, UserRole.DISPATCHER.value, db)


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Получить информацию о текущем пользователе (личный кабинет).
    
    Для всех ролей возвращает базовую информацию из auth-service.
    Для водителей дополнительно получает данные из driver-service (документы, авто, статус и т.д.).
    """
    # Базовая информация о пользователе
    base_response = {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "phone_number": current_user.phone_number,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "driver_data": None
    }
    
    # Если пользователь - водитель, получаем дополнительные данные из driver-service
    if current_user.role == UserRole.DRIVER.value:
        token = credentials.credentials
        driver_data = await get_driver_info(current_user.id, token)
        if driver_data:
            base_response["driver_data"] = driver_data
        else:
            logger.warning(f"Could not fetch driver data for user {current_user.id}")
    
    return UserProfileResponse(**base_response)


async def get_driver_info(driver_id: int, token: str) -> Optional[Dict[str, Any]]:
    """Получить информацию о водителе из driver-service"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.DRIVER_SERVICE_URL}/api/v1/drivers/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Failed to fetch driver info: {response.status_code}")
            return None
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching driver info for driver {driver_id}")
            return None
        except httpx.ConnectError:
            logger.error(f"Connection error to driver-service: {settings.DRIVER_SERVICE_URL}")
            return None
        except Exception as e:
            logger.error(f"Error fetching driver info: {e}", exc_info=True)
            return None


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить информацию о пользователе по ID (только для админов).
    Используется другими сервисами для получения полной информации о пользователе.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        phone_number=user.phone_number,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified
    )


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    role_request: UpdateRoleRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Изменить роль пользователя (только для админов)
    
    ВАЖНО: Для регистрации водителей используйте driver-service:
    POST /api/v1/drivers/register (в driver-service)
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Обновляем роль
    updated_user = await user_repo.update_user(
        user_id,
        role=role_request.role.value
    )
    
    return UserResponse(
        id=updated_user.id,
        full_name=updated_user.full_name,
        phone_number=updated_user.phone_number,
        email=updated_user.email,
        role=updated_user.role,
        is_active=updated_user.is_active,
        is_verified=updated_user.is_verified
    )




@router.patch("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Активировать пользователя (только для админов)
    """
    user_repo = UserRepository(db)
    success = await user_repo.activate_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user = await user_repo.get_by_id(user_id)
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        phone_number=user.phone_number,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified
    )


@router.patch("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Деактивировать пользователя (только для админов)
    """
    user_repo = UserRepository(db)
    success = await user_repo.deactivate_user(user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user = await user_repo.get_by_id(user_id)
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        phone_number=user.phone_number,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified
    )

