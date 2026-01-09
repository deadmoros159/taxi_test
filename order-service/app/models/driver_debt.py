from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class DriverDebt(Base):
    """Модель долга водителя"""
    __tablename__ = "driver_debts"

    id = Column(Integer, primary_key=True, index=True)
    
    # Связь с заказом
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    driver_id = Column(Integer, nullable=False, index=True)  # ID водителя из auth-service
    
    # Сумма долга
    amount = Column(Float, nullable=False)  # Сумма долга (20% от заказа)
    paid_amount = Column(Float, default=0.0, nullable=False)  # Сколько уже оплачено
    remaining_amount = Column(Float, nullable=False)  # Остаток долга
    
    # Статус
    is_paid = Column(Boolean, default=False, nullable=False, index=True)
    is_blocked = Column(Boolean, default=False, nullable=False, index=True)  # Заблокирован ли водитель
    
    # Даты
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    due_date = Column(DateTime(timezone=True), nullable=False)  # Срок оплаты (через неделю)
    paid_at = Column(DateTime(timezone=True), nullable=True)  # Когда оплачен
    blocked_at = Column(DateTime(timezone=True), nullable=True)  # Когда заблокирован
    
    # Примечания
    notes = Column(Text, nullable=True)  # Примечания о платеже
    
    # Связь с заказом
    order = relationship("Order", back_populates="debts")

