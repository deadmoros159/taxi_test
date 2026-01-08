from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DriverDebtResponse(BaseModel):
    """Схема ответа с информацией о долге"""
    id: int
    order_id: int
    driver_id: int
    amount: float
    paid_amount: float
    remaining_amount: float
    is_paid: bool
    is_blocked: bool
    created_at: datetime
    due_date: datetime
    paid_at: Optional[datetime] = None
    blocked_at: Optional[datetime] = None
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class DriverDebtCreate(BaseModel):
    """Схема создания долга"""
    order_id: int
    driver_id: int
    amount: float
    due_date: datetime

