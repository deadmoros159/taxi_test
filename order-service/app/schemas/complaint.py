from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.complaint import ComplaintType, ComplaintStatus


class ComplaintCreate(BaseModel):
    """Схема создания жалобы"""
    complaint_type: ComplaintType = Field(..., description="Тип жалобы")
    description: str = Field(..., min_length=10, description="Описание жалобы (минимум 10 символов)")
    media_ids: Optional[List[int]] = Field(None, description="ID медиа файлов из media-service")


class ComplaintResponse(BaseModel):
    """Схема ответа с информацией о жалобе"""
    id: int
    order_id: int
    complained_by: int
    complaint_type: ComplaintType
    description: str
    media_ids: Optional[List[int]] = None
    status: ComplaintStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    resolution_notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class ComplaintStatusUpdate(BaseModel):
    """Схема обновления статуса жалобы"""
    status: ComplaintStatus = Field(..., description="Новый статус жалобы")
    resolution_notes: Optional[str] = Field(None, description="Примечания при изменении статуса")

