"""
Endpoints для управления водителями и их автомобилями
"""
import sys
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response
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
    DriverFullRegisterRequest,
    DriverResponse,
    DriverStatusUpdate,
    VehicleUpdate,
    VehicleRegisterRequest,
    DriverMediaUpdate,
    VehicleResponse,
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


@router.get("/fleet/summary")
async def fleet_summary(
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Автопарк: сколько авто в БД и к каким водителям/пользователям привязаны"""
    from sqlalchemy import select, func
    from app.models.driver import Vehicle, Driver

    total = await db.execute(select(func.count(Vehicle.id)))
    total_count = int(total.scalar() or 0)

    rows = await db.execute(
        select(Vehicle.id, Vehicle.license_plate, Driver.id, Driver.user_id)
        .join(Driver, Driver.id == Vehicle.driver_id)
        .order_by(Vehicle.id.desc())
        .limit(200)
    )
    items = []
    for vehicle_id, license_plate, driver_id, user_id in rows.all():
        items.append(
            {
                "vehicle_id": vehicle_id,
                "license_plate": license_plate,
                "driver_id": driver_id,
                "user_id": user_id,
            }
        )

    return {"total_vehicles": total_count, "items": items}


@router.get("/fleet/vehicles/{vehicle_id}", tags=["Admin Panel"])
async def fleet_vehicle_detail(
    vehicle_id: int,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Автопарк: детальная информация по авто + привязка к водителю/пользователю"""
    from sqlalchemy import select
    from app.models.driver import Vehicle, Driver

    row = await db.execute(
        select(Vehicle, Driver)
        .join(Driver, Driver.id == Vehicle.driver_id)
        .where(Vehicle.id == vehicle_id)
    )
    result = row.first()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    vehicle, driver = result
    return {
        "vehicle": {
            "id": vehicle.id,
            "driver_id": vehicle.driver_id,
            "brand": vehicle.brand,
            "model": vehicle.model,
            "year": vehicle.year,
            "color": vehicle.color,
            "license_plate": vehicle.license_plate,
            "vin": vehicle.vin,
            "seats": vehicle.seats,
            "vehicle_type": vehicle.vehicle_type,
            "vehicle_photo_url": vehicle.vehicle_photo_url,
            "vehicle_photo_media_id": vehicle.vehicle_photo_media_id,
            "created_at": vehicle.created_at,
            "updated_at": vehicle.updated_at,
        },
        "driver": {
            "id": driver.id,
            "user_id": driver.user_id,
            "status": driver.status.value,
            "is_verified": driver.is_verified,
            "registered_by": driver.registered_by,
            "registered_at": driver.registered_at,
            "license_number": driver.license_number,
            "license_expiry": driver.license_expiry,
            "passport_number": driver.passport_number,
            "license_photo_media_id": driver.license_photo_media_id,
            "passport_photo_media_id": driver.passport_photo_media_id,
            "driver_photo_media_id": driver.driver_photo_media_id,
        },
    }

@router.post("/drivers/register", response_model=DriverResponse, status_code=status.HTTP_201_CREATED, tags=["Driver Registration"])
async def register_driver(
    request: DriverRegisterRequest,
    http_request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация водителя для существующего пользователя (только для диспетчеров и админов)
    
    Используется когда пользователь уже зарегистрирован в системе (как пассажир)
    и хочет стать водителем. Диспетчер дополняет данные (документы/авто) по user_id.
    
    Flow:
    1) Пользователь зарегистрировался как пассажир
    2) В приложении нажал "Стать водителем" и пришел в офис
    3) Диспетчер вызывает этот endpoint с user_id и данными водителя/авто
    4) Автоматически обновляется роль пользователя в auth-service на 'driver'
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
        vehicle_data=request.vehicle,
        license_photo_url=request.license_photo_url,
        passport_photo_url=request.passport_photo_url,
        driver_photo_url=request.driver_photo_url,
        license_photo_media_id=request.license_photo_media_id,
        passport_photo_media_id=request.passport_photo_media_id,
        driver_photo_media_id=request.driver_photo_media_id,
    )
    
    # Автоматически переводим пользователя в роль driver
    promoted = await auth_client.promote_user_to_driver(request.user_id, token)
    if not promoted:
        logger.warning(
            f"Driver created in driver-service but failed to promote user role in auth-service: user_id={request.user_id}"
        )
    
    logger.info(f"Driver registered for existing user {request.user_id} by dispatcher {dispatcher_id}")
    
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
        license_photo_url=driver.license_photo_url,
        passport_photo_url=driver.passport_photo_url,
        driver_photo_url=driver.driver_photo_url,
        license_photo_media_id=driver.license_photo_media_id,
        passport_photo_media_id=driver.passport_photo_media_id,
        driver_photo_media_id=driver.driver_photo_media_id,
        vehicle=driver.vehicle
    )


@router.post("/drivers/register-full", response_model=DriverResponse, status_code=status.HTTP_201_CREATED, tags=["Driver Registration"])
async def register_driver_full(
    request: DriverFullRegisterRequest,
    http_request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Полная регистрация водителя с нуля (только для диспетчеров и админов)
    
    Используется когда человек приходит в офис и регистрируется с нуля (не знает про приложение).
    Создается пользователь в auth-service, затем водитель в driver-service, затем автомобиль.
    
    Flow:
    1) Человек приходит в офис без аккаунта
    2) Диспетчер вводит все данные (ФИО, телефон, документы, авто)
    3) Создается пользователь в auth-service (верифицированный и активный)
    4) Создается водитель в driver-service с ролью 'driver'
    5) Создается автомобиль
    """
    driver_repo = DriverRepository(db)
    token = current_user.get("token", "")
    
    # Проверяем уникальность номера водительского удостоверения
    existing_license = await driver_repo.get_by_license(request.license_number)
    if existing_license:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License number already exists"
        )
    
    # Создаем пользователя в auth-service
    user_data = await auth_client.create_user_direct(
        full_name=request.full_name,
        phone_number=request.phone_number,
        email=request.email,
        token=token
    )
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create user in auth-service. User may already exist."
        )
    
    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User created but ID not returned from auth-service"
        )
    
    # Проверяем, не зарегистрирован ли уже этот пользователь как водитель
    existing_driver = await driver_repo.get_by_user_id(user_id)
    if existing_driver:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already registered as a driver"
        )
    
    # Получаем ID диспетчера
    dispatcher_id = current_user.get("id") or current_user.get("user_id")
    
    # Создаем водителя с автомобилем
    driver = await driver_repo.create_driver_with_vehicle(
        user_id=user_id,
        license_number=request.license_number,
        license_expiry=request.license_expiry,
        passport_number=request.passport_number,
        registered_by=dispatcher_id,
        vehicle_data=request.vehicle,
        license_photo_media_id=request.license_photo_media_id,
        passport_photo_media_id=request.passport_photo_media_id,
        driver_photo_media_id=request.driver_photo_media_id,
    )
    
    # Автоматически переводим пользователя в роль driver
    promoted = await auth_client.promote_user_to_driver(user_id, token)
    if not promoted:
        logger.warning(
            f"Driver created in driver-service but failed to promote user role in auth-service: user_id={user_id}"
        )
    
    logger.info(f"Driver registered from scratch: user_id={user_id}, driver_id={driver.id} by dispatcher {dispatcher_id}")
    
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
        license_photo_url=driver.license_photo_url,
        passport_photo_url=driver.passport_photo_url,
        driver_photo_url=driver.driver_photo_url,
        license_photo_media_id=driver.license_photo_media_id,
        passport_photo_media_id=driver.passport_photo_media_id,
        driver_photo_media_id=driver.driver_photo_media_id,
        vehicle=driver.vehicle
    )


@router.post("/drivers/{user_id}/promote-to-driver", response_model=DriverResponse, tags=["Driver Management"])
async def promote_user_to_driver(
    user_id: int,
    http_request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Перевести существующего пользователя в водители (только для диспетчеров и админов)
    
    Используется когда пользователь уже зарегистрирован как пассажир,
    но еще не зарегистрирован как водитель в driver-service.
    Просто обновляет роль в auth-service на 'driver'.
    
    ВАЖНО: Для полной регистрации водителя используйте /drivers/register или /drivers/register-full
    """
    token = current_user.get("token", "")
    
    # Проверяем, что пользователь существует
    user_exists = await auth_client.check_user_exists(user_id, token)
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in auth-service"
        )
    
    # Проверяем, не зарегистрирован ли уже как водитель
    driver_repo = DriverRepository(db)
    existing_driver = await driver_repo.get_by_user_id(user_id)
    if existing_driver:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already registered as a driver in driver-service"
        )
    
    # Переводим пользователя в роль driver
    promoted = await auth_client.promote_user_to_driver(user_id, token)
    if not promoted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to promote user to driver role in auth-service"
        )
    
    logger.info(f"User {user_id} promoted to driver role by {current_user.get('id')}")
    
    # Возвращаем информацию о пользователе (но не о водителе, т.к. он еще не зарегистрирован)
    user_info = await auth_client.get_user_info(user_id, token)
    
    raise HTTPException(
        status_code=status.HTTP_200_OK,
        detail=f"User {user_id} promoted to driver role. Use /drivers/register to complete driver registration."
    )


@router.post("/drivers/{driver_id}/vehicles", response_model=DriverResponse, status_code=status.HTTP_201_CREATED, tags=["Vehicle Management"])
async def register_vehicle_for_driver(
    driver_id: int,
    request: VehicleRegisterRequest,
    http_request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Зарегистрировать автомобиль для существующего водителя (только для диспетчеров и админов)
    
    Используется когда водитель уже зарегистрирован, но нужно добавить или обновить автомобиль.
    Если у водителя уже есть автомобиль, он будет обновлен.
    """
    driver_repo = DriverRepository(db)
    driver = await driver_repo.get_by_id(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Если у водителя уже есть автомобиль, обновляем его
    if driver.vehicle:
        vehicle = await driver_repo.update_vehicle(
            driver_id=driver_id,
            brand=request.vehicle.brand,
            model=request.vehicle.model,
            year=request.vehicle.year,
            color=request.vehicle.color,
            license_plate=request.vehicle.license_plate,
            vin=request.vehicle.vin,
            seats=request.vehicle.seats,
            vehicle_type=request.vehicle.vehicle_type,
            vehicle_photo_url=request.vehicle.vehicle_photo_url,
            vehicle_photo_media_id=request.vehicle.vehicle_photo_media_id,
        )
        logger.info(f"Vehicle updated for driver {driver_id}")
    else:
        # Создаем новый автомобиль
        from app.models.driver import Vehicle
        vehicle = Vehicle(
            driver_id=driver_id,
            brand=request.vehicle.brand,
            model=request.vehicle.model,
            year=request.vehicle.year,
            color=request.vehicle.color,
            license_plate=request.vehicle.license_plate,
            vin=request.vehicle.vin,
            seats=request.vehicle.seats,
            vehicle_type=request.vehicle.vehicle_type,
            vehicle_photo_url=request.vehicle.vehicle_photo_url,
            vehicle_photo_media_id=request.vehicle.vehicle_photo_media_id,
        )
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)
        logger.info(f"Vehicle created for driver {driver_id}")
    
    await db.refresh(driver)
    
    from app.schemas.driver import VehicleResponse
    vehicle_response = VehicleResponse(
        id=vehicle.id,
        brand=vehicle.brand,
        model=vehicle.model,
        year=vehicle.year,
        color=vehicle.color,
        license_plate=vehicle.license_plate,
        vin=vehicle.vin,
        seats=vehicle.seats,
        vehicle_type=vehicle.vehicle_type,
        vehicle_photo_url=vehicle.vehicle_photo_url,
        vehicle_photo_media_id=vehicle.vehicle_photo_media_id,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at
    )
    
    return DriverResponse(
        id=driver.id,
        user_id=driver.user_id,
        license_number=driver.license_number,
        license_expiry=driver.license_expiry,
        passport_number=driver.passport_number,
        license_photo_url=driver.license_photo_url,
        passport_photo_url=driver.passport_photo_url,
        driver_photo_url=driver.driver_photo_url,
        license_photo_media_id=driver.license_photo_media_id,
        passport_photo_media_id=driver.passport_photo_media_id,
        driver_photo_media_id=driver.driver_photo_media_id,
        status=driver.status.value,
        is_verified=driver.is_verified,
        registered_by=driver.registered_by,
        registered_at=driver.registered_at,
        vehicle=vehicle_response
    )


@router.get("/drivers", response_model=List[DriverResponse], tags=["Admin Panel"])
async def get_all_drivers(
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех водителей (для диспетчеров и админов)"""
    driver_repo = DriverRepository(db)
    drivers = await driver_repo.get_all()
    
    from app.schemas.driver import VehicleResponse
    
    result = []
    for driver in drivers:
        vehicle_response = None
        if driver.vehicle:
            vehicle_response = VehicleResponse(
                id=driver.vehicle.id,
                brand=driver.vehicle.brand,
                model=driver.vehicle.model,
                year=driver.vehicle.year,
                color=driver.vehicle.color,
                license_plate=driver.vehicle.license_plate,
                vin=driver.vehicle.vin,
                seats=driver.vehicle.seats,
                vehicle_type=driver.vehicle.vehicle_type,
                vehicle_photo_url=driver.vehicle.vehicle_photo_url,
                vehicle_photo_media_id=driver.vehicle.vehicle_photo_media_id,
                created_at=driver.vehicle.created_at,
                updated_at=driver.vehicle.updated_at
            )
        
        result.append(DriverResponse(
            id=driver.id,
            user_id=driver.user_id,
            license_number=driver.license_number,
            license_expiry=driver.license_expiry,
            passport_number=driver.passport_number,
            license_photo_url=driver.license_photo_url,
            passport_photo_url=driver.passport_photo_url,
            driver_photo_url=driver.driver_photo_url,
            license_photo_media_id=driver.license_photo_media_id,
            passport_photo_media_id=driver.passport_photo_media_id,
            driver_photo_media_id=driver.driver_photo_media_id,
            status=driver.status.value,
            is_verified=driver.is_verified,
            registered_by=driver.registered_by,
            registered_at=driver.registered_at,
            vehicle=vehicle_response
        ))
    
    return result


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
        license_photo_url=driver.license_photo_url,
        passport_photo_url=driver.passport_photo_url,
        driver_photo_url=driver.driver_photo_url,
        license_photo_media_id=driver.license_photo_media_id,
        passport_photo_media_id=driver.passport_photo_media_id,
        driver_photo_media_id=driver.driver_photo_media_id,
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
    
    from app.schemas.driver import VehicleResponse
    
    vehicle_response = None
    if updated_driver.vehicle:
        vehicle_response = VehicleResponse(
            id=updated_driver.vehicle.id,
            brand=updated_driver.vehicle.brand,
            model=updated_driver.vehicle.model,
            year=updated_driver.vehicle.year,
            color=updated_driver.vehicle.color,
            license_plate=updated_driver.vehicle.license_plate,
            vin=updated_driver.vehicle.vin,
            seats=updated_driver.vehicle.seats,
            vehicle_type=updated_driver.vehicle.vehicle_type,
            vehicle_photo_url=updated_driver.vehicle.vehicle_photo_url,
            vehicle_photo_media_id=updated_driver.vehicle.vehicle_photo_media_id,
            created_at=updated_driver.vehicle.created_at,
            updated_at=updated_driver.vehicle.updated_at
        )
    
    return DriverResponse(
        id=updated_driver.id,
        user_id=updated_driver.user_id,
        license_number=updated_driver.license_number,
        license_expiry=updated_driver.license_expiry,
        passport_number=updated_driver.passport_number,
        license_photo_url=updated_driver.license_photo_url,
        passport_photo_url=updated_driver.passport_photo_url,
        driver_photo_url=updated_driver.driver_photo_url,
        license_photo_media_id=updated_driver.license_photo_media_id,
        passport_photo_media_id=updated_driver.passport_photo_media_id,
        driver_photo_media_id=updated_driver.driver_photo_media_id,
        status=updated_driver.status.value,
        is_verified=updated_driver.is_verified,
        registered_by=updated_driver.registered_by,
        registered_at=updated_driver.registered_at,
        vehicle=vehicle_response
    )


@router.patch("/drivers/{driver_id}/vehicle", response_model=DriverResponse)
async def update_vehicle(
    driver_id: int,
    payload: VehicleUpdate,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Обновить данные автомобиля водителя (включая фото через media_id)"""
    driver_repo = DriverRepository(db)
    driver = await driver_repo.get_by_id(driver_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    vehicle = await driver_repo.update_vehicle(
        driver_id=driver_id,
        brand=payload.brand,
        model=payload.model,
        year=payload.year,
        color=payload.color,
        license_plate=payload.license_plate,
        vin=payload.vin,
        seats=payload.seats,
        vehicle_type=payload.vehicle_type,
        vehicle_photo_url=payload.vehicle_photo_url,
        vehicle_photo_media_id=payload.vehicle_photo_media_id,
    )
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    await db.refresh(driver)
    return DriverResponse(
        id=driver.id,
        user_id=driver.user_id,
        license_number=driver.license_number,
        license_expiry=driver.license_expiry,
        passport_number=driver.passport_number,
        license_photo_url=driver.license_photo_url,
        passport_photo_url=driver.passport_photo_url,
        driver_photo_url=driver.driver_photo_url,
        license_photo_media_id=driver.license_photo_media_id,
        passport_photo_media_id=driver.passport_photo_media_id,
        driver_photo_media_id=driver.driver_photo_media_id,
        status=driver.status.value,
        is_verified=driver.is_verified,
        registered_by=driver.registered_by,
        registered_at=driver.registered_at,
        vehicle=vehicle,
    )


@router.patch("/drivers/{driver_id}/media", response_model=DriverResponse)
async def update_driver_media(
    driver_id: int,
    payload: DriverMediaUpdate,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Обновить медиа (ID) документов/фото водителя"""
    driver_repo = DriverRepository(db)
    updated_driver = await driver_repo.update_driver_media(
        driver_id,
        license_photo_media_id=payload.license_photo_media_id,
        passport_photo_media_id=payload.passport_photo_media_id,
        driver_photo_media_id=payload.driver_photo_media_id,
    )
    if not updated_driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    return DriverResponse(
        id=updated_driver.id,
        user_id=updated_driver.user_id,
        license_number=updated_driver.license_number,
        license_expiry=updated_driver.license_expiry,
        passport_number=updated_driver.passport_number,
        license_photo_url=updated_driver.license_photo_url,
        passport_photo_url=updated_driver.passport_photo_url,
        driver_photo_url=updated_driver.driver_photo_url,
        license_photo_media_id=updated_driver.license_photo_media_id,
        passport_photo_media_id=updated_driver.passport_photo_media_id,
        driver_photo_media_id=updated_driver.driver_photo_media_id,
        status=updated_driver.status.value,
        is_verified=updated_driver.is_verified,
        registered_by=updated_driver.registered_by,
        registered_at=updated_driver.registered_at,
        vehicle=updated_driver.vehicle,
    )


# ==================== ADMIN PANEL ENDPOINTS ====================

@router.get("/admin/drivers/{driver_id}", response_model=DriverResponse, tags=["Admin Panel"])
async def get_driver_by_id_admin(
    driver_id: int,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Получить информацию о водителе по ID (для админ-панели)"""
    driver_repo = DriverRepository(db)
    driver = await driver_repo.get_by_id(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    from app.schemas.driver import VehicleResponse
    
    vehicle_response = None
    if driver.vehicle:
        vehicle_response = VehicleResponse(
            id=driver.vehicle.id,
            brand=driver.vehicle.brand,
            model=driver.vehicle.model,
            year=driver.vehicle.year,
            color=driver.vehicle.color,
            license_plate=driver.vehicle.license_plate,
            vin=driver.vehicle.vin,
            seats=driver.vehicle.seats,
            vehicle_type=driver.vehicle.vehicle_type,
            vehicle_photo_url=driver.vehicle.vehicle_photo_url,
            vehicle_photo_media_id=driver.vehicle.vehicle_photo_media_id,
            created_at=driver.vehicle.created_at,
            updated_at=driver.vehicle.updated_at
        )
    
    return DriverResponse(
        id=driver.id,
        user_id=driver.user_id,
        license_number=driver.license_number,
        license_expiry=driver.license_expiry,
        passport_number=driver.passport_number,
        license_photo_url=driver.license_photo_url,
        passport_photo_url=driver.passport_photo_url,
        driver_photo_url=driver.driver_photo_url,
        license_photo_media_id=driver.license_photo_media_id,
        passport_photo_media_id=driver.passport_photo_media_id,
        driver_photo_media_id=driver.driver_photo_media_id,
        status=driver.status.value,
        is_verified=driver.is_verified,
        registered_by=driver.registered_by,
        registered_at=driver.registered_at,
        vehicle=vehicle_response
    )


@router.delete("/admin/drivers/{driver_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin Panel"])
async def delete_driver_admin(
    driver_id: int,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Удалить водителя (для админ-панели)"""
    driver_repo = DriverRepository(db)
    driver = await driver_repo.get_by_id(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    success = await driver_repo.delete_driver(driver_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete driver"
        )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/vehicles", response_model=List[VehicleResponse], tags=["Admin Panel"])
async def get_all_vehicles_admin(
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех автомобилей (для админ-панели)"""
    driver_repo = DriverRepository(db)
    vehicles = await driver_repo.get_all_vehicles()
    
    return [
        VehicleResponse(
            id=v.id,
            brand=v.brand,
            model=v.model,
            year=v.year,
            color=v.color,
            license_plate=v.license_plate,
            vin=v.vin,
            seats=v.seats,
            vehicle_type=v.vehicle_type,
            vehicle_photo_url=v.vehicle_photo_url,
            vehicle_photo_media_id=v.vehicle_photo_media_id,
            created_at=v.created_at,
            updated_at=v.updated_at
        )
        for v in vehicles
    ]


@router.get("/admin/vehicles/{vehicle_id}", response_model=VehicleResponse, tags=["Admin Panel"])
async def get_vehicle_by_id_admin(
    vehicle_id: int,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Получить информацию об автомобиле по ID (для админ-панели)"""
    driver_repo = DriverRepository(db)
    vehicle = await driver_repo.get_vehicle_by_id(vehicle_id)
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    
    return VehicleResponse(
        id=vehicle.id,
        brand=vehicle.brand,
        model=vehicle.model,
        year=vehicle.year,
        color=vehicle.color,
        license_plate=vehicle.license_plate,
        vin=vehicle.vin,
        seats=vehicle.seats,
        vehicle_type=vehicle.vehicle_type,
        vehicle_photo_url=vehicle.vehicle_photo_url,
        vehicle_photo_media_id=vehicle.vehicle_photo_media_id,
        created_at=vehicle.created_at,
        updated_at=vehicle.updated_at
    )


@router.delete("/admin/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin Panel"])
async def delete_vehicle_admin(
    vehicle_id: int,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Удалить автомобиль (для админ-панели)"""
    driver_repo = DriverRepository(db)
    vehicle = await driver_repo.get_vehicle_by_id(vehicle_id)
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    
    success = await driver_repo.delete_vehicle(vehicle_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete vehicle"
        )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)
