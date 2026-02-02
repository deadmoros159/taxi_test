from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from app.models.driver import DriverStatus


class VehicleCreate(BaseModel):
    """Схема для создания автомобиля"""
    brand: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=50)
    year: int = Field(..., ge=1900, le=2100)
    color: str = Field(..., min_length=1, max_length=30)
    license_plate: str = Field(..., min_length=1, max_length=20)
    vin: Optional[str] = Field(None, max_length=17)
    seats: int = Field(4, ge=2, le=20)
    vehicle_type: str = Field(..., min_length=1, max_length=30)
    vehicle_photo_url: Optional[str] = Field(None, description="(legacy) URL фото автомобиля")
    vehicle_photo_media_id: Optional[int] = Field(None, description="Media ID фото автомобиля (media-service)")
    vehicle_photo_media_id: Optional[int] = Field(None, description="ID медиа (tag=vehicle_photo) из media-service")


class DriverRegisterRequest(BaseModel):
    """Запрос на регистрацию водителя (от диспетчера)"""
    user_id: int = Field(..., description="ID пользователя из auth-service")
    license_number: str = Field(..., min_length=1, max_length=50)
    license_expiry: datetime
    passport_number: str = Field(..., min_length=1, max_length=50)
    license_photo_url: Optional[str] = Field(None, description="(legacy) URL фото водительских прав")
    passport_photo_url: Optional[str] = Field(None, description="(legacy) URL фото паспорта")
    driver_photo_url: Optional[str] = Field(None, description="(legacy) URL фото водителя")
    license_photo_media_id: Optional[int] = Field(None, description="Media ID фото прав (media-service)")
    passport_photo_media_id: Optional[int] = Field(None, description="Media ID фото паспорта (media-service)")
    driver_photo_media_id: Optional[int] = Field(None, description="Media ID фото водителя (media-service)")
    license_photo_media_id: Optional[int] = Field(None, description="ID медиа (tag=document) фото прав")
    passport_photo_media_id: Optional[int] = Field(None, description="ID медиа (tag=document) фото паспорта")
    driver_photo_media_id: Optional[int] = Field(None, description="ID медиа (tag=profile_photo) фото водителя")
    vehicle: VehicleCreate


class VehicleResponse(BaseModel):
    """Ответ с информацией об автомобиле"""
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
    vehicle_photo_media_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DriverResponse(BaseModel):
    """Ответ с информацией о водителе"""
    id: int
    user_id: int
    license_number: str
    license_expiry: datetime
    passport_number: str
    license_photo_url: Optional[str]
    passport_photo_url: Optional[str]
    driver_photo_url: Optional[str]
    license_photo_media_id: Optional[int] = None
    passport_photo_media_id: Optional[int] = None
    driver_photo_media_id: Optional[int] = None
    license_photo_media_id: Optional[int] = None
    passport_photo_media_id: Optional[int] = None
    driver_photo_media_id: Optional[int] = None
    status: str
    is_verified: bool
    registered_by: Optional[int]
    registered_at: datetime
    vehicle: Optional[VehicleResponse]

    class Config:
        from_attributes = True


class DriverStatusUpdate(BaseModel):
    """Обновление статуса водителя"""
    status: DriverStatus


class VehicleUpdate(BaseModel):
    """Обновление информации об автомобиле"""
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
    """Обновление медиа-идентификаторов документов/фото водителя"""
    license_photo_media_id: Optional[int] = None
    passport_photo_media_id: Optional[int] = None
    driver_photo_media_id: Optional[int] = None
    vehicle_photo_url: Optional[str] = None
    vehicle_photo_media_id: Optional[int] = None


class FleetStatsResponse(BaseModel):
    total_vehicles: int


class FleetVehicleItem(BaseModel):
    vehicle_id: int
    driver_id: int
    user_id: int
    brand: str
    model: str
    license_plate: str


