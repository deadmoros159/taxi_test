from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class OrderStatus(str, enum.Enum):
    """Статусы заказа"""
    PENDING = "pending"              # Ожидает водителя
    ACCEPTED = "accepted"            # Принят водителем
    DRIVER_ARRIVED = "driver_arrived" # Водитель прибыл
    IN_PROGRESS = "in_progress"      # В пути
    COMPLETED = "completed"          # Завершен
    CANCELLED = "cancelled"          # Отменен
    CANCELLED_BY_DRIVER = "cancelled_by_driver"  # Отменен водителем
    CANCELLED_BY_PASSENGER = "cancelled_by_passenger"  # Отменен пассажиром


class Order(Base):
    """Модель заказа"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    
    # Пользователи
    passenger_id = Column(Integer, nullable=False, index=True)  # ID пассажира из auth-service
    driver_id = Column(Integer, nullable=True, index=True)  # ID водителя (назначается при принятии)
    
    # Локации
    start_latitude = Column(Float, nullable=False)
    start_longitude = Column(Float, nullable=False)
    start_address = Column(String, nullable=False)  # Адрес отправления
    
    end_latitude = Column(Float, nullable=True)  # Может быть не указан при создании
    end_longitude = Column(Float, nullable=True)
    end_address = Column(String, nullable=True)  # Адрес назначения
    
    # Информация о заказе
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False, index=True)
    price = Column(Float, nullable=True)  # Цена заказа (рассчитывается или устанавливается)
    estimated_time_minutes = Column(Integer, nullable=True)  # Оценка времени до клиента в минутах
    
    # Фактические данные поездки
    actual_distance_km = Column(Float, nullable=True)  # Фактическое расстояние в км
    actual_time_minutes = Column(Integer, nullable=True)  # Фактическое время поездки в минутах
    route_history = Column(Text, nullable=True)  # История маршрута (JSON строка с координатами)
    
    # Информация о водителе (когда заказ принят)
    driver_location_lat = Column(Float, nullable=True)  # Текущее местоположение водителя
    driver_location_lng = Column(Float, nullable=True)
    vehicle_info = Column(String, nullable=True)  # Информация об автомобиле (JSON или строка)
    
    # Отмена заказа
    cancellation_reason = Column(Text, nullable=True)  # Причина отмены (обязательна при отмене)
    cancelled_by = Column(Integer, nullable=True)  # ID пользователя, который отменил
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)  # Когда водитель принял заказ
    completed_at = Column(DateTime(timezone=True), nullable=True)  # Когда заказ завершен
    cancelled_at = Column(DateTime(timezone=True), nullable=True)  # Когда заказ отменен

    # Запланированное время выполнения заказа (для отложенных заказов)
    # Если None — считаем, что заказ "на сейчас"
    order_date = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Связь с долгами
    debts = relationship("DriverDebt", back_populates="order", cascade="all, delete-orphan")
    
    # Связь с жалобами
    complaints = relationship("Complaint", back_populates="order", cascade="all, delete-orphan")
    
    # Связь с оценками
    ratings = relationship("Rating", back_populates="order", cascade="all, delete-orphan")


