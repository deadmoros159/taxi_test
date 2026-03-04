from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.models.media import MediaTag


class MediaUploadResponse(BaseModel):
    media_id: int = Field(..., description="ID загруженного файла")
    filename: str = Field(..., description="Имя файла")
    mime_type: str = Field(..., description="MIME тип файла")
    size_bytes: int = Field(..., description="Размер файла в байтах")
    tag: MediaTag = Field(..., description="Тег медиа")
    url: str = Field(..., description="URL для получения файла")
    created_at: datetime = Field(..., description="Дата загрузки")


class MediaInfoResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    uploaded_by: Optional[int] = None
    tag: MediaTag
    url: str = Field(..., description="Полный URL для получения файла")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


