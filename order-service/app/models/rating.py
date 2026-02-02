from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Rating(Base):
    """Модель оценки/рейтинга"""
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, index=True)
    
    # Связь с заказом
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True, unique=True)  # Один рейтинг на заказ
    
    # Кто оценивает (пассажир)
    passenger_id = Column(Integer, nullable=False, index=True)  # ID пассажира, который оставил оценку
    
    # Кого оценивают (всегда водитель из заказа)
    driver_id = Column(Integer, nullable=False, index=True)  # ID водителя, которого оценивают
    
    # Оценка
    rating = Column(Integer, nullable=False)  # Оценка от 1 до 5
    comment = Column(Text, nullable=True)  # Комментарий (опционально)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связь с заказом
    order = relationship("Order", back_populates="ratings")

