from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RatingCreate(BaseModel):
    """Схема создания оценки"""
    rating: int = Field(..., ge=1, le=5, description="Оценка от 1 до 5")
    comment: Optional[str] = Field(None, description="Комментарий к оценке")


class RatingResponse(BaseModel):
    """Схема ответа с информацией об оценке"""
    id: int
    order_id: int
    passenger_id: int  # Кто оценил (пассажир)
    driver_id: int  # Кого оценили (водитель)
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RatingStatsResponse(BaseModel):
    """Схема статистики оценок водителя"""
    user_id: int  # ID водителя
    average_rating: float  # Средняя оценка
    total_ratings: int  # Общее количество оценок
    ratings_breakdown: dict[int, int]  # {1: count, 2: count, 3: count, 4: count, 5: count}

