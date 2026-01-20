"""
Endpoints для управления пользователями и ролями
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel

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

router = APIRouter()
staff_router = APIRouter()


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

    user = await user_repo.create_user(
        email=str(payload.email),
        full_name=payload.full_name,
        role=UserRole.DISPATCHER.value,
        is_active=True,
        is_verified=True,
        password_hash=hash_password(payload.password),
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

    if not verify_password(payload.password, user.password_hash):
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
        expires_in=900,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
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


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Получить информацию о текущем пользователе"""
    return UserResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        phone_number=current_user.phone_number,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified
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

