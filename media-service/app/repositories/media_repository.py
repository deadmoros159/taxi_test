from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.models.media import MediaFile
import logging

logger = logging.getLogger(__name__)


class MediaRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_media_file(
        self,
        filename: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        s3_key: str,
        tag,
        uploaded_by: Optional[int] = None,
    ) -> MediaFile:
        """Создать запись о файле в БД"""
        media_file = MediaFile(
            filename=filename,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            s3_key=s3_key,
            tag=tag,
            uploaded_by=uploaded_by,
        )
        self.db.add(media_file)
        await self.db.commit()
        await self.db.refresh(media_file)
        return media_file

    async def get_by_id(self, media_id: int) -> Optional[MediaFile]:
        """Получить файл по ID"""
        stmt = select(MediaFile).where(MediaFile.id == media_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_s3_key(self, s3_key: str) -> Optional[MediaFile]:
        """Получить файл по S3 ключу"""
        stmt = select(MediaFile).where(MediaFile.s3_key == s3_key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_media_file(self, media_id: int) -> bool:
        """Удалить запись о файле из БД"""
        media_file = await self.get_by_id(media_id)
        if not media_file:
            return False
        await self.db.delete(media_file)
        await self.db.commit()
        return True

