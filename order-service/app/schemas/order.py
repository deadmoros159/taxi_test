from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.order import OrderStatus


class OrderCreate(BaseModel):
    """Схема создания заказа"""
    start_latitude: float = Field(..., description="Широта точки отправления")
    start_longitude: float = Field(..., description="Долгота точки отправления")
    start_address: str = Field(..., description="Адрес отправления")
    end_latitude: Optional[float] = Field(None, description="Широта точки назначения")
    end_longitude: Optional[float] = Field(None, description="Долгота точки назначения")
    end_address: Optional[str] = Field(None, description="Адрес назначения")


class OrderResponse(BaseModel):
    """Схема ответа с информацией о заказе"""
    id: int
    passenger_id: int
    driver_id: Optional[int] = None
    start_latitude: float
    start_longitude: float
    start_address: str
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    end_address: Optional[str] = None
    status: OrderStatus
    price: Optional[float] = None
    estimated_time_minutes: Optional[int] = None
    driver_location_lat: Optional[float] = None
    driver_location_lng: Optional[float] = None
    vehicle_info: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class OrderUpdate(BaseModel):
    """Схема обновления заказа"""
    status: Optional[OrderStatus] = None
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    end_address: Optional[str] = None
    price: Optional[float] = None


class OrderCancel(BaseModel):
    """Схема отмены заказа"""
    reason: str = Field(..., min_length=10, description="Причина отмены (минимум 10 символов)")


class OrderAccept(BaseModel):
    """Схема принятия заказа водителем"""
    driver_location_lat: float = Field(..., description="Текущая широта водителя")
    driver_location_lng: float = Field(..., description="Текущая долгота водителя")

