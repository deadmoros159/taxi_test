from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class DriverStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    ON_ORDER = "on_order"
    OFFLINE = "offline"
    BLOCKED = "blocked"


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    license_number = Column(String, unique=True, nullable=False, index=True)
    license_expiry = Column(DateTime(timezone=True), nullable=False)
    passport_number = Column(String, nullable=False)
    
    license_photo_url = Column(String, nullable=True)
    passport_photo_url = Column(String, nullable=True)
    driver_photo_url = Column(String, nullable=True)
    license_photo_media_id = Column(Integer, nullable=True, index=True)
    passport_photo_media_id = Column(Integer, nullable=True, index=True)
    driver_photo_media_id = Column(Integer, nullable=True, index=True)
    
    status = Column(SQLEnum(DriverStatus), default=DriverStatus.PENDING, nullable=False, index=True)
    is_verified = Column(Boolean, default=False)
    registered_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    vehicle = relationship("Vehicle", back_populates="driver", uselist=False, cascade="all, delete-orphan")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, unique=True, index=True)
    
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    color = Column(String, nullable=False)
    license_plate = Column(String, unique=True, nullable=False, index=True)
    vin = Column(String, unique=True, nullable=True)
    seats = Column(Integer, default=4, nullable=False)
    vehicle_type = Column(String, nullable=False)
    vehicle_photo_url = Column(String, nullable=True)
    vehicle_photo_media_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    driver = relationship("Driver", back_populates="vehicle")

