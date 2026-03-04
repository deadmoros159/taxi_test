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
    # Дата и время заказа (опционально, если не указано - используется текущее время)
    order_date: Optional[datetime] = Field(None, description="Дата и время заказа (если не указано, используется текущее время)")


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
    actual_distance_km: Optional[float] = None
    actual_time_minutes: Optional[int] = None
    driver_location_lat: Optional[float] = None
    driver_location_lng: Optional[float] = None
    vehicle_info: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    order_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class OrderCancel(BaseModel):
    """Схема отмены заказа"""
    reason: str = Field(..., min_length=10, description="Причина отмены (минимум 10 символов)")


class OrderAccept(BaseModel):
    """Схема принятия заказа водителем"""
    driver_location_lat: float = Field(..., description="Текущая широта водителя")
    driver_location_lng: float = Field(..., description="Текущая долгота водителя")


class OrderStatusUpdate(BaseModel):
    """Схема обновления статуса заказа"""
    status: OrderStatus = Field(..., description="Новый статус заказа")


class OrderLocationUpdate(BaseModel):
    """Схема обновления местоположения водителя"""
    latitude: float = Field(..., description="Широта")
    longitude: float = Field(..., description="Долгота")


class OrderCompleteData(BaseModel):
    """Схема данных для завершения заказа"""
    actual_distance_km: Optional[float] = Field(None, description="Фактическое расстояние в км")
    actual_time_minutes: Optional[int] = Field(None, description="Фактическое время поездки в минутах")
    end_latitude: Optional[float] = Field(None, description="Финальная широта")
    end_longitude: Optional[float] = Field(None, description="Финальная долгота")
    end_address: Optional[str] = Field(None, description="Финальный адрес")


class OrderDetailAdminResponse(BaseModel):
    """Детальная информация о заказе для админа (с полной информацией о пользователях)"""
    # Информация о заказе
    id: int
    status: OrderStatus
    price: Optional[float] = None
    estimated_time_minutes: Optional[int] = None
    start_latitude: float
    start_longitude: float
    start_address: str
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    end_address: Optional[str] = None
    vehicle_info: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    order_date: Optional[datetime] = None
    
    # Полная информация о пассажире
    passenger_id: int
    passenger_full_name: Optional[str] = None
    passenger_phone: Optional[str] = None
    passenger_email: Optional[str] = None
    
    # Полная информация о водителе
    driver_id: Optional[int] = None
    driver_full_name: Optional[str] = None
    driver_phone: Optional[str] = None
    driver_email: Optional[str] = None
    driver_location_lat: Optional[float] = None
    driver_location_lng: Optional[float] = None
    
    class Config:
        from_attributes = True


