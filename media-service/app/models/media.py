from sqlalchemy import Column, Integer, String, DateTime, BigInteger
from sqlalchemy.sql import func
from app.core.database import Base


class MediaFile(Base):
    """Модель для хранения метаданных файлов"""
    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)  # Размер в байтах
    s3_key = Column(String, nullable=False, unique=True, index=True)  # Ключ в S3/MinIO
    uploaded_by = Column(Integer, nullable=True)  # ID пользователя из auth-service (без ForeignKey, т.к. таблица users в другой БД)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

