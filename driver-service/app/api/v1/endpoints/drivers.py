import sys
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

shared_path = os.path.join(os.path.dirname(__file__), '../../../../shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from app.core.database import get_db
from app.schemas.driver import (
    DriverRegisterRequest,
    DriverFullRegisterRequest,
    DriverResponse,
    DriverListResponse,
    DriverStatusUpdate,
    VehicleUpdate,
    VehicleRegisterRequest,
    DriverMediaUpdate,
    VehicleResponse,
    DriverRatingInfo,
    DriverDebtInfo,
    DriverUserInfo,
    DRIVER_STATUS_DISPLAY,
)
from app.repositories.driver_repository import DriverRepository
from app.models.driver import Driver, DriverStatus
from app.services.auth_client import auth_client
from app.services.order_client import order_client
from correlation import get_correlation_id, set_correlation_id

logger = logging.getLogger(__name__)

security = HTTPBearer(description="Bearer токен из auth-service (получить через /api/v1/auth/login)")

router = APIRouter(
    dependencies=[Depends(security)],
    responses={401: {"description": "Требуется авторизация (Bearer токен)"}},
)


async def get_current_user_from_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Проверка токена через auth-service. Требуется роль admin, dispatcher или driver."""
    correlation_id = request.headers.get("X-Correlation-ID")
    if correlation_id:
        set_correlation_id(correlation_id)
    else:
        set_correlation_id()

    token = credentials.credentials
    user_data = await auth_client.verify_token(token)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = user_data.get("role")
    if role not in ["dispatcher", "admin", "driver"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    user_data["token"] = token
    return user_data


def require_dispatcher_or_admin(
    request: Request,
    current_user: dict = Depends(get_current_user_from_token)
):
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
    role = current_user.get("role")
    if role not in ["driver", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access this endpoint"
        )
    return current_user


def _summary_to_response_fields(summary):
    """Из ответа order-service /drivers/{id}/summary собрать rating, balance, debt_info для DriverResponse."""
    if not summary:
        return None, None, None
    rating_data = summary.get("rating")
    rating = (
        DriverRatingInfo(
            average_rating=rating_data["average_rating"],
            total_ratings=rating_data["total_ratings"],
        )
        if rating_data
        else None
    )
    balance = summary.get("balance")
    debt = summary.get("debt_info")
    debt_info = (
        DriverDebtInfo(
            is_blocked=debt.get("is_blocked", False),
            has_overdue=debt.get("has_overdue", False),
            overdue_count=debt.get("overdue_count", 0),
        )
        if debt
        else None
    )
    return rating, balance, debt_info


def _vehicle_to_response(vehicle):
    """Собрать VehicleResponse из модели Vehicle или None."""
    if not vehicle:
        return None
    from app.schemas.driver import VehicleResponse
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
        updated_at=vehicle.updated_at,
    )


def _user_to_driver_user_info(user_data: dict, driver_id: Optional[int] = None):
    """Из ответа auth-service собрать DriverUserInfo. Если передан driver_id, имя 'User'/пустое заменяется на 'Водитель #id'."""
    if not user_data:
        return None
    raw_name = user_data.get("full_name", "") or ""
    full_name = _normalize_driver_display_name(raw_name, driver_id) if driver_id else raw_name
    return DriverUserInfo(
        id=user_data.get("id"),
        full_name=full_name,
        phone_number=user_data.get("phone_number"),
        email=user_data.get("email"),
    )


async def _driver_to_response(driver, token: str = None, current_user_data: dict = None):
    """
    Собрать сущность водителя (DriverResponse): user (данные из auth), рейтинг, баланс, задолженность.
    current_user_data: если передан и user_id совпадает — используем для user (для /me не нужен запрос в auth).
    token: для order-service summary и для auth get_user_info (админ/диспетчер).
    """
    vehicle_response = _vehicle_to_response(driver.vehicle)
    rating, balance, debt_info = None, None, None
    user_info = None
    if current_user_data and current_user_data.get("id") == driver.user_id:
        user_info = _user_to_driver_user_info(current_user_data, driver.id)
    elif token:
        user_data = await auth_client.get_user_info(driver.user_id, token)
        user_info = _user_to_driver_user_info(user_data, driver.id)
    if token:
        summary = await order_client.get_driver_summary(driver.user_id, token)
        rating, balance, debt_info = _summary_to_response_fields(summary)
    status_val = driver.status.value
    return DriverResponse(
        id=driver.id,
        user=user_info,
        license_number=driver.license_number,
        license_expiry=driver.license_expiry,
        passport_number=driver.passport_number,
        license_photo_url=driver.license_photo_url,
        passport_photo_url=driver.passport_photo_url,
        driver_photo_url=driver.driver_photo_url,
        license_photo_media_id=driver.license_photo_media_id,
        passport_photo_media_id=driver.passport_photo_media_id,
        driver_photo_media_id=driver.driver_photo_media_id,
        status=status_val,
        status_display=DRIVER_STATUS_DISPLAY.get(status_val),
        is_verified=driver.is_verified,
        registered_by=driver.registered_by,
        registered_at=driver.registered_at,
        vehicle=vehicle_response,
        rating=rating,
        balance=balance,
        debt_info=debt_info,
    )


def _normalize_driver_display_name(full_name: str, driver_id: int) -> str:
    """Если имя пустое или дефолтное 'User' — подставить 'Водитель #id'."""
    if not full_name or (full_name or "").strip() in ("", "User"):
        return f"Водитель #{driver_id}"
    return (full_name or "").strip()


async def _driver_to_list_response(driver, token: str = None):
    """Собрать карточку водителя для списка: имя, машина с госномером, рейтинг, баланс, статус."""
    full_name = ""
    if token:
        user_data = await auth_client.get_user_info(driver.user_id, token)
        if user_data:
            full_name = user_data.get("full_name", "")
    full_name = _normalize_driver_display_name(full_name, driver.id)
    vehicle_display = ""
    if driver.vehicle:
        v = driver.vehicle
        vehicle_display = f"{v.brand} {v.model} ({v.license_plate})"
    rating, balance, debt_info = None, None, None
    if token:
        summary = await order_client.get_driver_summary(driver.user_id, token)
        rating, balance, debt_info = _summary_to_response_fields(summary)
    status_val = driver.status.value
    return DriverListResponse(
        id=driver.id,
        full_name=full_name,
        vehicle_display=vehicle_display,
        rating=rating,
        balance=balance,
        debt_info=debt_info,
        status=status_val,
        status_display=DRIVER_STATUS_DISPLAY.get(status_val),
    )


@router.get("/fleet/summary")
async def fleet_summary(
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
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
    Единственная ручка «сделать пользователя водителем» для уже существующего user.

    Создаёт запись водителя и ТС в driver-service и выставляет роль driver в auth.
    Вызывать только эту ручку (или register-full для регистрации с нуля). Диспетчер/админ.
    """
    driver_repo = DriverRepository(db)
    
    existing_driver = await driver_repo.get_by_user_id(request.user_id)
    if existing_driver:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already registered as a driver"
        )
    
    existing_license = await driver_repo.get_by_license(request.license_number)
    if existing_license:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License number already exists"
        )
    existing_plate = await driver_repo.get_vehicle_by_license_plate(request.vehicle.license_plate)
    if existing_plate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle with this license plate already registered"
        )
    if request.vehicle.vin:
        existing_vin = await driver_repo.get_vehicle_by_vin(request.vehicle.vin)
        if existing_vin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vehicle with this VIN already registered"
            )
    token = current_user.get("token", "")
    user_exists = await auth_client.check_user_exists(request.user_id, token)
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in auth-service"
        )
    
    dispatcher_id = current_user.get("id") or current_user.get("user_id")
    
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
    
    promoted, err_status, err_detail = await auth_client.promote_user_to_driver(request.user_id, token)
    if not promoted:
        raise HTTPException(
            status_code=err_status or 502,
            detail=err_detail or "Не удалось выставить роль driver в auth-service. Проверьте логи.",
        )
    logger.info(f"Driver registered for existing user {request.user_id} by dispatcher {dispatcher_id}")
    
    return await _driver_to_response(driver, token)


@router.post("/drivers/register-full", response_model=DriverResponse, status_code=status.HTTP_201_CREATED, tags=["Driver Registration"])
async def register_driver_full(
    request: DriverFullRegisterRequest,
    http_request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация водителя с нуля: создаёт user в auth, затем водителя и ТС в driver-service.

    Единственная ручка «создать нового человека и сразу сделать водителем». Диспетчер/админ.
    """
    driver_repo = DriverRepository(db)
    token = current_user.get("token", "")
    
    existing_license = await driver_repo.get_by_license(request.license_number)
    if existing_license:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License number already exists"
        )
    existing_plate = await driver_repo.get_vehicle_by_license_plate(request.vehicle.license_plate)
    if existing_plate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle with this license plate already registered"
        )
    if request.vehicle.vin:
        existing_vin = await driver_repo.get_vehicle_by_vin(request.vehicle.vin)
        if existing_vin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vehicle with this VIN already registered"
            )
    user_data, auth_error_status, auth_error_detail = await auth_client.create_user_direct(
        full_name=request.full_name,
        phone_number=request.phone_number,
        email=request.email,
        token=token,
        role="driver",
    )
    if auth_error_status is not None:
        raise HTTPException(
            status_code=min(auth_error_status, 599) if auth_error_status else 502,
            detail=auth_error_detail or "Failed to create user in auth-service."
        )
    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User created but ID not returned from auth-service"
        )
    
    existing_driver = await driver_repo.get_by_user_id(user_id)
    if existing_driver:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already registered as a driver"
        )
    
    dispatcher_id = current_user.get("id") or current_user.get("user_id")
    
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
    # Роль driver уже выставлена при создании user (role=driver в create_user_direct)
    logger.info(f"Driver registered from scratch: user_id={user_id}, driver_id={driver.id} by dispatcher {dispatcher_id}")
    
    return await _driver_to_response(driver, token)


@router.post("/drivers/{driver_id}/vehicles", response_model=DriverResponse, status_code=status.HTTP_201_CREATED, tags=["Vehicle Management"])
async def register_vehicle_for_driver(
    driver_id: int,
    request: VehicleRegisterRequest,
    http_request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    driver_repo = DriverRepository(db)
    driver = await driver_repo.get_by_id(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
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
    token = current_user.get("token", "")
    return await _driver_to_response(driver, token)


@router.get("/drivers", response_model=List[DriverListResponse], tags=["Admin Panel"])
async def get_all_drivers(
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    """Список водителей для карточек: имя, машина с госномером, рейтинг, задолженность, статус."""
    driver_repo = DriverRepository(db)
    drivers = await driver_repo.get_all()
    token = current_user.get("token", "")
    result = []
    for driver in drivers:
        result.append(await _driver_to_list_response(driver, token))
    return result


@router.get("/drivers/me", response_model=DriverResponse)
async def get_my_driver_info(
    request: Request,
    current_user: dict = Depends(require_driver),
    db: AsyncSession = Depends(get_db)
):
    driver_repo = DriverRepository(db)
    user_id = current_user.get("id") or current_user.get("user_id")
    driver = await driver_repo.get_by_user_id(user_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    token = current_user.get("token", "")
    return await _driver_to_response(driver, token, current_user_data=current_user)


@router.post("/drivers/me/start-work", response_model=DriverResponse, tags=["Driver Status"])
async def driver_start_work(
    request: Request,
    current_user: dict = Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    """Водитель выходит на линию (статус → active)."""
    driver_repo = DriverRepository(db)
    user_id = current_user.get("id") or current_user.get("user_id")
    driver = await driver_repo.get_by_user_id(user_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    updated = await driver_repo.update_status(driver.id, DriverStatus.ACTIVE)
    token = current_user.get("token", "")
    return await _driver_to_response(updated, token)


@router.post("/drivers/me/end-work", response_model=DriverResponse, tags=["Driver Status"])
async def driver_end_work(
    request: Request,
    current_user: dict = Depends(require_driver),
    db: AsyncSession = Depends(get_db),
):
    """Водитель заканчивает смену (статус → offline)."""
    driver_repo = DriverRepository(db)
    user_id = current_user.get("id") or current_user.get("user_id")
    driver = await driver_repo.get_by_user_id(user_id)
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    updated = await driver_repo.update_status(driver.id, DriverStatus.OFFLINE)
    token = current_user.get("token", "")
    return await _driver_to_response(updated, token)


@router.patch("/drivers/{driver_id}/status", response_model=DriverResponse)
async def update_driver_status(
    driver_id: int,
    status_update: DriverStatusUpdate,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    driver_repo = DriverRepository(db)
    driver = await driver_repo.get_by_id(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    updated_driver = await driver_repo.update_status(driver_id, status_update.status)
    token = current_user.get("token", "")
    return await _driver_to_response(updated_driver, token)


@router.patch("/drivers/{driver_id}/vehicle", response_model=DriverResponse)
async def update_vehicle(
    driver_id: int,
    payload: VehicleUpdate,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
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
    token = current_user.get("token", "")
    return await _driver_to_response(driver, token)


@router.patch("/drivers/{driver_id}/media", response_model=DriverResponse)
async def update_driver_media(
    driver_id: int,
    payload: DriverMediaUpdate,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    driver_repo = DriverRepository(db)
    updated_driver = await driver_repo.update_driver_media(
        driver_id,
        license_photo_media_id=payload.license_photo_media_id,
        passport_photo_media_id=payload.passport_photo_media_id,
        driver_photo_media_id=payload.driver_photo_media_id,
    )
    if not updated_driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    token = current_user.get("token", "")
    return await _driver_to_response(updated_driver, token)


@router.get("/admin/drivers/{driver_id}", response_model=DriverResponse, tags=["Admin Panel"])
async def get_driver_by_id_admin(
    driver_id: int,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
    driver_repo = DriverRepository(db)
    driver = await driver_repo.get_by_id(driver_id)
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    token = current_user.get("token", "")
    return await _driver_to_response(driver, token)


@router.delete("/admin/drivers/{driver_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin Panel"])
async def delete_driver_admin(
    driver_id: int,
    request: Request,
    current_user: dict = Depends(require_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db)
):
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
