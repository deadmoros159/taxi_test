"""
Endpoints для управления пользователями и ролями
"""
from fastapi import APIRouter, Depends, HTTPException, status
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

router = APIRouter()


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


@router.post("/users/{user_id}/register-dispatcher", response_model=UserResponse)
async def register_dispatcher(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Зарегистрировать пользователя как диспетчера (только для админов)
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Назначаем роль диспетчера
    updated_user = await user_repo.update_user(
        user_id,
        role=UserRole.DISPATCHER.value
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


@router.post("/users/{user_id}/register-admin", response_model=UserResponse)
async def register_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Зарегистрировать пользователя как админа (только для существующих админов)
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Назначаем роль админа
    updated_user = await user_repo.update_user(
        user_id,
        role=UserRole.ADMIN.value
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

