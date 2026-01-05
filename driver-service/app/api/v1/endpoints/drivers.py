"""
Endpoints для управления водителями и их автомобилями
"""
import sys
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import logging

# Добавляем shared library в путь
shared_path = os.path.join(os.path.dirname(__file__), '../../../../shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from app.core.database import get_db
from app.schemas.driver import (
    DriverRegisterRequest,
    DriverResponse,
    DriverStatusUpdate,
    VehicleUpdate
)
from app.repositories.driver_repository import DriverRepository
from app.models.driver import Driver, DriverStatus
from app.services.auth_client import auth_client
from correlation import get_correlation_id, set_correlation_id

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_current_user_from_token(
    request: Request,
    authorization: str = Depends(lambda: None)
):
    """
    Получить текущего пользователя из токена
    
    Использует ResilientHTTPClient с Circuit Breaker и Retry Logic
    """
    # Устанавливаем correlation ID из заголовка или генерируем новый
    correlation_id = request.headers.get("X-Correlation-ID")
    if correlation_id:
        set_correlation_id(correlation_id)
    else:
        set_correlation_id()
    
    # Получаем токен из заголовка Authorization
    if not authorization:
        authorization = request.headers.get("Authorization", "")
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    user_data = await auth_client.verify_token(token)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    # Проверяем роль
    role = user_data.get("role")
    if role not in ["dispatcher", "admin", "driver"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Сохраняем токен для дальнейшего использования
    user_data["token"] = token
    
    return user_data


def require_dispatcher_or_admin(
    request: Request,
    current_user: dict = Depends(get_current_user_from_token)
):
    """Только диспетчеры и админы"""
    role = current_user.get("role")
    if role not in ["dispatcher", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only dispatchers and admins can access this endpoint"
        )
    return current_user


def require_driver(
    request: Request,
    current_user: dict = Depends(get_current_user_from_token)
):
    """Только водители"""
    role = current_user.get("role")
    if role not in ["driver", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access this endpoint"
        )
    return current_user


@router.post("/drivers/register", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
async def register_driver(
    request: DriverRegisterRequest,
    http_request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация водителя с автомобилем (только для диспетчеров и админов)
    
    Диспетчер регистрирует пользователя как водителя и добавляет его автомобиль.
    
    ВАЖНО: Роль пользователя НЕ изменяется автоматически в auth-service.
    Это должно быть сделано отдельно через админ-панель или через событие.
    Это соблюдает принцип независимости микросервисов.
    """
    driver_repo = DriverRepository(db)
    
    # Проверяем, не зарегистрирован ли уже этот пользователь как водитель
    existing_driver = await driver_repo.get_by_user_id(request.user_id)
    if existing_driver:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already registered as a driver"
        )
    
    # Проверяем уникальность номера водительского удостоверения
    existing_license = await driver_repo.get_by_license(request.license_number)
    if existing_license:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License number already exists"
        )
    
    # Проверяем, что пользователь существует в auth-service
    # (но НЕ изменяем его роль - это нарушит независимость сервисов)
    token = current_user.get("token", "")
    user_exists = await auth_client.check_user_exists(request.user_id, token)
    
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in auth-service"
        )
    
    # Получаем ID диспетчера
    dispatcher_id = current_user.get("id") or current_user.get("user_id")
    
    # Создаем водителя с автомобилем
    driver = await driver_repo.create_driver_with_vehicle(
        user_id=request.user_id,
        license_number=request.license_number,
        license_expiry=request.license_expiry,
        passport_number=request.passport_number,
        registered_by=dispatcher_id,
        vehicle_data=request.vehicle
    )
    
    # Логируем, что нужно обновить роль в auth-service
    # В будущем это можно сделать через событие (Event-Driven)
    logger.info(
        f"Driver registered: user_id={request.user_id}, driver_id={driver.id}. "
        f"NOTE: User role should be updated to 'driver' in auth-service separately. "
        f"Use PATCH /api/v1/users/{request.user_id}/role in auth-service."
    )
    
    return DriverResponse(
        id=driver.id,
        user_id=driver.user_id,
        license_number=driver.license_number,
        license_expiry=driver.license_expiry,
        passport_number=driver.passport_number,
        status=driver.status.value,
        is_verified=driver.is_verified,
        registered_by=driver.registered_by,
        registered_at=driver.registered_at,
        vehicle=driver.vehicle
    )


@router.get("/drivers", response_model=List[DriverResponse])
async def get_all_drivers(
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех водителей (для диспетчеров и админов)"""
    driver_repo = DriverRepository(db)
    drivers = await driver_repo.get_all()
    
    return [
        DriverResponse(
            id=driver.id,
            user_id=driver.user_id,
            license_number=driver.license_number,
            license_expiry=driver.license_expiry,
            passport_number=driver.passport_number,
            status=driver.status.value,
            is_verified=driver.is_verified,
            registered_by=driver.registered_by,
            registered_at=driver.registered_at,
            vehicle=driver.vehicle
        )
        for driver in drivers
    ]


@router.get("/drivers/me", response_model=DriverResponse)
async def get_my_driver_info(
    request: Request,
    current_user: dict = Depends(require_driver),
    db: AsyncSession = Depends(get_db)
):
    """Получить информацию о себе (для водителей)"""
    driver_repo = DriverRepository(db)
    user_id = current_user.get("id") or current_user.get("user_id")
    driver = await driver_repo.get_by_user_id(user_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    return DriverResponse(
        id=driver.id,
        user_id=driver.user_id,
        license_number=driver.license_number,
        license_expiry=driver.license_expiry,
        passport_number=driver.passport_number,
        status=driver.status.value,
        is_verified=driver.is_verified,
        registered_by=driver.registered_by,
        registered_at=driver.registered_at,
        vehicle=driver.vehicle
    )


@router.patch("/drivers/{driver_id}/status", response_model=DriverResponse)
async def update_driver_status(
    driver_id: int,
    status_update: DriverStatusUpdate,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Изменить статус водителя (для диспетчеров и админов)"""
    driver_repo = DriverRepository(db)
    driver = await driver_repo.get_by_id(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    updated_driver = await driver_repo.update_status(driver_id, status_update.status)
    
    return DriverResponse(
        id=updated_driver.id,
        user_id=updated_driver.user_id,
        license_number=updated_driver.license_number,
        license_expiry=updated_driver.license_expiry,
        passport_number=updated_driver.passport_number,
        status=updated_driver.status.value,
        is_verified=updated_driver.is_verified,
        registered_by=updated_driver.registered_by,
        registered_at=updated_driver.registered_at,
        vehicle=updated_driver.vehicle
    )
