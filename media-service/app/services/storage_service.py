from minio import Minio
from minio.error import S3Error
from app.core.config import settings
import logging
import uuid
from typing import Optional, Tuple
from io import BytesIO

logger = logging.getLogger(__name__)


class StorageService:
    """Сервис для работы с MinIO (S3-совместимое хранилище)"""

    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME
        # Bucket будет создан при первом использовании или в lifespan

    def ensure_bucket_exists(self):
        """Создать bucket, если его нет (вызывается при старте сервиса)"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
            else:
                logger.info(f"Bucket {self.bucket_name} already exists")
        except S3Error as e:
            # BucketAlreadyOwnedByYou - это не ошибка, bucket уже существует
            if "BucketAlreadyOwnedByYou" in str(e):
                logger.info(f"Bucket {self.bucket_name} already exists (owned by you)")
            else:
                logger.error(f"Error ensuring bucket exists: {e}")
                raise

    def generate_s3_key(self, original_filename: str, user_id: Optional[int] = None) -> str:
        """Генерировать уникальный ключ для S3"""
        # Формат: {user_id}/{uuid}.{extension}
        # Если user_id нет, используем "anonymous"
        file_ext = original_filename.split(".")[-1] if "." in original_filename else ""
        unique_id = str(uuid.uuid4())
        prefix = f"user_{user_id}" if user_id else "anonymous"
        return f"{prefix}/{unique_id}.{file_ext}" if file_ext else f"{prefix}/{unique_id}"

    async def upload_file(
        self,
        file_data: bytes,
        s3_key: str,
        mime_type: str,
    ) -> bool:
        """Загрузить файл в MinIO"""
        try:
            file_stream = BytesIO(file_data)
            file_stream.seek(0)
            
            self.client.put_object(
                self.bucket_name,
                s3_key,
                file_stream,
                length=len(file_data),
                content_type=mime_type,
            )
            logger.info(f"File uploaded to S3: {s3_key}")
            return True
        except S3Error as e:
            logger.error(f"Error uploading file to S3: {e}")
            return False

    async def get_file(self, s3_key: str) -> Optional[Tuple[bytes, str]]:
        """Получить файл из MinIO. Возвращает (file_data, mime_type)"""
        try:
            response = self.client.get_object(self.bucket_name, s3_key)
            file_data = response.read()
            mime_type = response.headers.get("Content-Type", "application/octet-stream")
            response.close()
            response.release_conn()
            return file_data, mime_type
        except S3Error as e:
            logger.error(f"Error getting file from S3: {e}")
            return None

    async def delete_file(self, s3_key: str) -> bool:
        """Удалить файл из MinIO"""
        try:
            self.client.remove_object(self.bucket_name, s3_key)
            logger.info(f"File deleted from S3: {s3_key}")
            return True
        except S3Error as e:
            logger.error(f"Error deleting file from S3: {e}")
            return False

    def get_file_url(self, media_id: int) -> str:
        """Получить URL для доступа к файлу"""
        # В production можно использовать presigned URLs для безопасности
        return f"/api/v1/media/{media_id}"


# Глобальный экземпляр
storage_service = StorageService()

