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


class DriverRegisterRequest(BaseModel):
    """Запрос на регистрацию водителя (от диспетчера)"""
    user_id: int = Field(..., description="ID пользователя из auth-service")
    license_number: str = Field(..., min_length=1, max_length=50)
    license_expiry: datetime
    passport_number: str = Field(..., min_length=1, max_length=50)
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

