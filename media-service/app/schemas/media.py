from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class MediaUploadResponse(BaseModel):
    """Ответ после загрузки файла"""
    media_id: int = Field(..., description="ID загруженного файла")
    filename: str = Field(..., description="Имя файла")
    mime_type: str = Field(..., description="MIME тип файла")
    size_bytes: int = Field(..., description="Размер файла в байтах")
    url: str = Field(..., description="URL для получения файла")
    created_at: datetime = Field(..., description="Дата загрузки")


class MediaInfoResponse(BaseModel):
    """Метаданные файла"""
    id: int
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    uploaded_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MediaFileResponse(BaseModel):
    """Полная информация о файле (для админов)"""
    id: int
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    s3_key: str
    uploaded_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

