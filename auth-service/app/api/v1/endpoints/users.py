from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
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
    photo_id: int | None = None  # ID фото профиля в media-service
    
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
    photo_id: int | None = None  # ID фото профиля в media-service
    # Дополнительные данные для водителя (если роль = driver)
    driver_data: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


@staff_router.post("/staff/dispatcher/register", response_model=UserResponse, tags=["Staff Management"])
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


@staff_router.post("/staff/dispatcher/login", response_model=TokensResponse, tags=["Staff Management"])
async def dispatcher_login(
    request: Request,
    payload: StaffLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Вход диспетчера по email/password (публичная)"""
    # rate limit (если Redis недоступен — в prod может упасть; в вашем rate_limiter он в prod строгий)
    await rate_limiter.check_request_limit(request, f"dispatcher_login:{payload.email}")
    return await _staff_login_for_role(payload, UserRole.DISPATCHER.value, db)


@router.get("/me", response_model=UserProfileResponse, tags=["Profile"])
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
        "photo_id": current_user.photo_id,
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


class UpdateProfilePhotoRequest(BaseModel):
    """Запрос на обновление фото профиля"""
    photo_id: int = Field(..., description="ID фото профиля в media-service")


@router.patch("/me/profile-photo", response_model=UserProfileResponse, tags=["Profile"])
async def update_profile_photo(
    request_data: UpdateProfilePhotoRequest,
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить фото профиля пользователя.
    
    Требуется авторизация. Пользователь может обновить только свое фото профиля.
    """
    # Обновляем photo_id
    current_user.photo_id = request_data.photo_id
    
    await db.commit()
    await db.refresh(current_user)
    
    # Формируем ответ
    base_response = {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "phone_number": current_user.phone_number,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "photo_id": current_user.photo_id,
        "driver_data": None
    }
    
    # Если пользователь - водитель, получаем дополнительные данные
    if current_user.role == UserRole.DRIVER.value:
        token = credentials.credentials
        driver_data = await get_driver_info(current_user.id, token)
        if driver_data:
            base_response["driver_data"] = driver_data
    
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


@router.get("/{user_id}", response_model=UserResponse, tags=["User Management"])
async def get_user_by_id(
    user_id: int,
    current_user: User = Depends(require_dispatcher),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить информацию о пользователе по ID (админ или диспетчер).
    Используется driver-service и другими сервисами для отображения имени и контактов.
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
        is_verified=user.is_verified,
        photo_id=user.photo_id
    )


@router.patch("/{user_id}/role", response_model=UserResponse, tags=["User Management"])
async def update_user_role(
    user_id: int,
    role_request: UpdateRoleRequest,
    current_user: User = Depends(require_driver_management),
    db: AsyncSession = Depends(get_db)
):
    """
    Изменить роль пользователя.

    - Роль driver: диспетчер или админ (вызывается из driver-service при регистрации водителя).
    - Другие роли (admin, dispatcher, passenger): только админ.

    Чтобы сделать пользователя водителем, используйте только driver-service:
    POST https://xhap.ru/driver/api/v1/drivers/register (существующий user)
    или POST .../drivers/register-full (создать user и водителя с нуля).
    """
    if role_request.role != UserRole.DRIVER and current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can change role to non-driver",
        )
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    updated_user = await user_repo.update_user(
        user_id,
        role=role_request.role.value,
    )
    return UserResponse(
        id=updated_user.id,
        full_name=updated_user.full_name,
        phone_number=updated_user.phone_number,
        email=updated_user.email,
        role=updated_user.role,
        is_active=updated_user.is_active,
        is_verified=updated_user.is_verified,
        photo_id=updated_user.photo_id,
    )


class CreateUserRequest(BaseModel):
    """Запрос на создание пользователя напрямую (для офисной регистрации)"""
    full_name: str = Field(..., min_length=1, max_length=100)
    phone_number: str = Field(..., min_length=10, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    role: Optional[UserRole] = Field(None, description="Роль при создании: driver — для регистрации водителя с нуля, иначе passenger")


@router.post("/create", response_model=UserResponse, tags=["User Management"])
async def create_user_direct(
    request_data: CreateUserRequest,
    current_user: User = Depends(require_driver_management),
    db: AsyncSession = Depends(get_db),
):
    """
    Создать пользователя напрямую (для офисной регистрации водителей).
    Пользователь создается верифицированным и активным.
    role=driver — создать сразу водителем (вызов из driver-service register-full).
    """
    user_repo = UserRepository(db)
    existing_phone = await user_repo.get_by_phone(request_data.phone_number)
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this phone number already exists",
        )
    if request_data.email:
        existing_email = await user_repo.get_by_email(request_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists",
            )
    # Диспетчер/админ могут создать только passenger или driver
    create_role = request_data.role if request_data.role in (UserRole.PASSENGER, UserRole.DRIVER) else UserRole.PASSENGER
    user = await user_repo.create_user(
        phone_number=request_data.phone_number,
        email=request_data.email,
        full_name=request_data.full_name,
        is_verified=True,
        is_active=True,
        role=create_role.value,
    )
    
    logger.info(f"User created directly by {current_user.id}: {user.id} - {request_data.phone_number}")
    
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        phone_number=user.phone_number,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        photo_id=user.photo_id
    )




@router.patch("/users/{user_id}/activate", response_model=UserResponse, tags=["User Management"])
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
        is_verified=user.is_verified,
        photo_id=user.photo_id
    )


@router.patch("/users/{user_id}/deactivate", response_model=UserResponse, tags=["User Management"])
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
        is_verified=user.is_verified,
        photo_id=user.photo_id
    )


@router.get("/admin/users", response_model=List[UserResponse], tags=["Admin Panel"])
async def get_all_users_admin(
    role: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список всех пользователей (для админ-панели).
    
    Доступ:
    - Диспетчеры: могут видеть только пассажиров (role=passenger)
    - Админы: могут видеть всех пользователей, включая фильтрацию по роли
    """
    user_role = current_user.role
    
    # Диспетчеры могут видеть только пассажиров
    if user_role == UserRole.DISPATCHER.value:
        if role and role != UserRole.PASSENGER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Dispatchers can only view passengers"
            )
        role = UserRole.PASSENGER.value
    
    # Админы не могут видеть сотрудников через этот endpoint (используйте /admin/staff)
    if user_role == UserRole.ADMIN.value and role == UserRole.DISPATCHER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /admin/staff endpoint to view dispatchers"
        )
    
    user_repo = UserRepository(db)
    users = await user_repo.get_all_users(role=role, limit=limit, offset=offset)
    
    return [
        UserResponse(
            id=user.id,
            full_name=user.full_name,
            phone_number=user.phone_number,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified
        )
        for user in users
    ]


@router.get("/admin/users/{user_id}", response_model=UserResponse, tags=["Admin Panel"])
async def get_user_by_id_admin(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить пользователя по ID (для админ-панели).
    
    Доступ:
    - Диспетчеры: могут видеть только пассажиров
    - Админы: могут видеть всех пользователей
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Диспетчеры могут видеть только пассажиров
    if current_user.role == UserRole.DISPATCHER.value and user.role != UserRole.PASSENGER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dispatchers can only view passengers"
        )
    
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        phone_number=user.phone_number,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        photo_id=user.photo_id
    )


@router.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin Panel"])
async def delete_user_admin(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить пользователя (для админ-панели).
    
    Доступ:
    - Диспетчеры: могут удалять только пассажиров
    - Админы: могут удалять всех пользователей (кроме других админов)
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Диспетчеры могут удалять только пассажиров
    if current_user.role == UserRole.DISPATCHER.value and user.role != UserRole.PASSENGER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dispatchers can only delete passengers"
        )
    
    # Админы не могут удалять других админов
    if current_user.role == UserRole.ADMIN.value and user.role == UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot delete other admins"
        )
    
    success = await user_repo.delete_user(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )
    
    from fastapi.responses import Response
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/staff", response_model=List[UserResponse], tags=["Admin Panel"])
async def get_all_staff_admin(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список всех сотрудников (диспетчеры) (только для админов).
    """
    user_repo = UserRepository(db)
    staff = await user_repo.get_users_by_role(UserRole.DISPATCHER.value, limit=limit, offset=offset)
    
    return [
        UserResponse(
            id=user.id,
            full_name=user.full_name,
            phone_number=user.phone_number,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified
        )
        for user in staff
    ]


@router.get("/admin/staff/{user_id}", response_model=UserResponse, tags=["Admin Panel"])
async def get_staff_by_id_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить сотрудника (диспетчера) по ID (только для админов).
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.role != UserRole.DISPATCHER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a dispatcher"
        )
    
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        phone_number=user.phone_number,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        photo_id=user.photo_id
    )


@router.delete("/admin/staff/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Admin Panel"])
async def delete_staff_admin(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить сотрудника (диспетчера) (только для админов).
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user.role != UserRole.DISPATCHER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a dispatcher"
        )
    
    success = await user_repo.delete_user(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete staff member"
        )
    
    from fastapi.responses import Response
    return Response(status_code=status.HTTP_204_NO_CONTENT)
