from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from app.models.driver import DriverStatus


class VehicleCreate(BaseModel):
    brand: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=50)
    year: int = Field(..., ge=1900, le=2100)
    color: str = Field(..., min_length=1, max_length=30)
    license_plate: str = Field(..., min_length=1, max_length=20)
    vin: Optional[str] = Field(None, max_length=17)
    seats: int = Field(4, ge=2, le=20)
    vehicle_type: str = Field(..., min_length=1, max_length=30)
    vehicle_photo_url: Optional[str] = Field(None, description="(legacy) URL фото автомобиля")
    vehicle_photo_media_id: Optional[int] = Field(None, description="ID медиа (tag=vehicle_photo) из media-service")


class DriverRegisterRequest(BaseModel):
    user_id: int = Field(..., description="ID пользователя из auth-service")
    license_number: str = Field(..., min_length=1, max_length=50)
    license_expiry: datetime
    passport_number: str = Field(..., min_length=1, max_length=50)
    license_photo_url: Optional[str] = Field(None, description="(legacy) URL фото водительских прав")
    passport_photo_url: Optional[str] = Field(None, description="(legacy) URL фото паспорта")
    driver_photo_url: Optional[str] = Field(None, description="(legacy) URL фото водителя")
    license_photo_media_id: Optional[int] = Field(None, description="ID медиа (tag=document) фото прав")
    passport_photo_media_id: Optional[int] = Field(None, description="ID медиа (tag=document) фото паспорта")
    driver_photo_media_id: Optional[int] = Field(None, description="ID медиа (tag=profile_photo) фото водителя")
    vehicle: VehicleCreate


class DriverFullRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100, description="Полное имя")
    phone_number: str = Field(..., min_length=10, max_length=20, description="Номер телефона")
    email: Optional[str] = Field(None, max_length=100)
    license_number: str = Field(..., min_length=1, max_length=50, description="Номер водительского удостоверения")
    license_expiry: datetime = Field(..., description="Срок действия прав")
    passport_number: str = Field(..., min_length=1, max_length=50)
    license_photo_media_id: Optional[int] = Field(None)
    passport_photo_media_id: Optional[int] = Field(None)
    driver_photo_media_id: Optional[int] = Field(None)
    vehicle: VehicleCreate


class VehicleResponse(BaseModel):
    id: int
    brand: str
    model: str
    year: int
    color: str
    license_plate: str
    vin: Optional[str]
    seats: int
    vehicle_type: str
    vehicle_photo_url: Optional[str]
    vehicle_photo_media_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DriverRatingInfo(BaseModel):
    """Рейтинг водителя (из order-service)."""
    average_rating: float
    total_ratings: int


class DriverDebtInfo(BaseModel):
    """Информация о просрочке/задолженности (из order-service)."""
    is_blocked: bool
    has_overdue: bool
    overdue_count: int


class DriverUserInfo(BaseModel):
    """Данные пользователя (из auth-service), вместо user_id."""
    id: int
    full_name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None


# Человекочитаемые подписи статусов для UI (На линии / Не на линии и т.д.)
DRIVER_STATUS_DISPLAY = {
    "pending": "Ожидает",
    "active": "На линии",
    "on_order": "На заказе",
    "offline": "Не на линии",
    "blocked": "Заблокирован",
}


class DriverListResponse(BaseModel):
    """Сокращённый ответ для списка водителей (карточки в UI)."""
    id: int
    full_name: str
    vehicle_display: str
    rating: Optional[DriverRatingInfo] = None
    balance: Optional[float] = None
    debt_info: Optional[DriverDebtInfo] = None
    status: str
    status_display: Optional[str] = None


class DriverResponse(BaseModel):
    id: int
    user: Optional[DriverUserInfo] = None
    license_number: str
    license_expiry: datetime
    passport_number: str
    license_photo_url: Optional[str]
    passport_photo_url: Optional[str]
    driver_photo_url: Optional[str]
    license_photo_media_id: Optional[int] = None
    passport_photo_media_id: Optional[int] = None
    driver_photo_media_id: Optional[int] = None
    status: str
    status_display: Optional[str] = None
    is_verified: bool
    registered_by: Optional[int]
    registered_at: datetime
    vehicle: Optional[VehicleResponse]
    rating: Optional[DriverRatingInfo] = None
    balance: Optional[float] = None
    debt_info: Optional[DriverDebtInfo] = None

    class Config:
        from_attributes = True


class DriverStatusUpdate(BaseModel):
    status: DriverStatus


class VehicleUpdate(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None
    license_plate: Optional[str] = None
    vin: Optional[str] = None
    seats: Optional[int] = None
    vehicle_type: Optional[str] = None
    vehicle_photo_url: Optional[str] = None
    vehicle_photo_media_id: Optional[int] = None


class DriverMediaUpdate(BaseModel):
    license_photo_media_id: Optional[int] = None
    passport_photo_media_id: Optional[int] = None
    driver_photo_media_id: Optional[int] = None


class VehicleRegisterRequest(BaseModel):
    vehicle: VehicleCreate


