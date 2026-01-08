from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class DriverStatus(str, enum.Enum):
    """Статусы водителя"""
    PENDING = "pending"          # Ожидает активации
    ACTIVE = "active"             # Активен, может принимать заказы
    ON_ORDER = "on_order"         # На заказе
    OFFLINE = "offline"           # Офлайн
    BLOCKED = "blocked"           # Заблокирован


class Driver(Base):
    """Модель водителя"""
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    # Документы
    license_number = Column(String, unique=True, nullable=False, index=True)
    license_expiry = Column(DateTime(timezone=True), nullable=False)
    passport_number = Column(String, nullable=False)
    
    # Фото документов (URL или путь к файлу)
    license_photo_url = Column(String, nullable=True)  # Фото водительских прав
    passport_photo_url = Column(String, nullable=True)  # Фото паспорта
    driver_photo_url = Column(String, nullable=True)  # Фото водителя
    
    # Статус
    status = Column(SQLEnum(DriverStatus), default=DriverStatus.PENDING, nullable=False, index=True)
    is_verified = Column(Boolean, default=False)  # Проверен ли диспетчером
    
    # Метаданные
    registered_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # ID диспетчера
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связь с автомобилем
    vehicle = relationship("Vehicle", back_populates="driver", uselist=False, cascade="all, delete-orphan")


class Vehicle(Base):
    """Модель автомобиля"""
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, unique=True, index=True)
    
    # Основная информация
    brand = Column(String, nullable=False)  # Марка (Toyota, Chevrolet и т.д.)
    model = Column(String, nullable=False)  # Модель (Camry, Malibu и т.д.)
    year = Column(Integer, nullable=False)   # Год выпуска
    color = Column(String, nullable=False)  # Цвет
    
    # Регистрационные данные
    license_plate = Column(String, unique=True, nullable=False, index=True)  # Гос. номер
    vin = Column(String, unique=True, nullable=True)  # VIN номер (опционально)
    
    # Технические характеристики
    seats = Column(Integer, default=4, nullable=False)  # Количество мест
    vehicle_type = Column(String, nullable=False)  # Тип (sedan, suv, minivan и т.д.)
    
    # Фото автомобиля
    vehicle_photo_url = Column(String, nullable=True)  # Фото автомобиля
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связь с водителем
    driver = relationship("Driver", back_populates="vehicle")

