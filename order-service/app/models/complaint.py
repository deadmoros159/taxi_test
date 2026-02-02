from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Text, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class ComplaintType(str, enum.Enum):
    """Типы жалоб"""
    DRIVER_BEHAVIOR = "driver_behavior"  # Поведение водителя
    ROUTE_ISSUE = "route_issue"           # Проблема с маршрутом
    PAYMENT_ISSUE = "payment_issue"       # Проблема с оплатой
    OTHER = "other"                       # Другое


class ComplaintStatus(str, enum.Enum):
    """Статусы жалобы"""
    PENDING = "pending"      # Ожидает рассмотрения
    REVIEWED = "reviewed"    # Рассмотрена
    RESOLVED = "resolved"    # Решена
    REJECTED = "rejected"    # Отклонена


class Complaint(Base):
    """Модель жалобы"""
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    
    # Связь с заказом
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    
    # Кто подал жалобу
    complained_by = Column(Integer, nullable=False, index=True)  # ID пользователя (passenger_id или driver_id)
    
    # Тип и описание жалобы
    complaint_type = Column(SQLEnum(ComplaintType), nullable=False)
    description = Column(Text, nullable=False)
    
    # Медиа файлы (ID из media-service)
    media_ids = Column(ARRAY(Integer), nullable=True)  # Список ID медиа файлов
    
    # Статус жалобы
    status = Column(SQLEnum(ComplaintStatus), default=ComplaintStatus.PENDING, nullable=False, index=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)  # Когда жалоба решена
    resolved_by = Column(Integer, nullable=True)  # ID админа, который решил жалобу
    resolution_notes = Column(Text, nullable=True)  # Примечания админа при решении
    
    # Связь с заказом
    order = relationship("Order", back_populates="complaints")

