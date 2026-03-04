from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Header, Request, Form
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging
from io import BytesIO
from urllib.parse import quote

from app.core.database import get_db
from app.core.config import settings
from app.repositories.media_repository import MediaRepository
from app.services.storage_service import storage_service
from app.services.auth_client import AuthClient
from app.schemas.media import MediaUploadResponse, MediaInfoResponse
from app.models.media import MediaTag

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    token = credentials.credentials
    auth_client = AuthClient()
    try:
        user_data = await auth_client.verify_token(token)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_data
    finally:
        await auth_client.close()


@router.post("/upload", response_model=MediaUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    tag: MediaTag = Form(MediaTag.DOCUMENT),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Загрузить файл (требуется авторизация).
    
    Ограничения:
    - Максимальный размер: 5 МБ
    - Разрешенные типы: изображения (JPEG, PNG, GIF, WebP), PDF, документы Word
    """
    MAX_SIZE_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    file_data = await file.read()
    file_size = len(file_data)
    
    if file_size > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB"
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {mime_type} is not allowed. Allowed types: {', '.join(settings.ALLOWED_MIME_TYPES)}"
        )
    
    user_id = current_user.get("id")
    s3_key = storage_service.generate_s3_key(file.filename or "file", user_id)
    
    upload_success = await storage_service.upload_file(
        file_data=file_data,
        s3_key=s3_key,
        mime_type=mime_type,
    )
    
    if not upload_success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage"
        )
    
    media_repo = MediaRepository(db)
    media_file = await media_repo.create_media_file(
        filename=s3_key.split("/")[-1],
        original_filename=file.filename or "file",
        mime_type=mime_type,
        size_bytes=file_size,
        s3_key=s3_key,
        tag=tag,
        uploaded_by=user_id,
    )
    
    # Генерируем полный URL
    if settings.MEDIA_BASE_URL:
        media_url = f"{settings.MEDIA_BASE_URL}{settings.API_V1_PREFIX}/media/{media_file.id}"
    elif request:
        base_url = str(request.base_url).rstrip("/")
        media_url = f"{base_url}{settings.API_V1_PREFIX}/media/{media_file.id}"
    else:
        media_url = f"{settings.API_V1_PREFIX}/media/{media_file.id}"
    
    return MediaUploadResponse(
        media_id=media_file.id,
        filename=media_file.filename,
        mime_type=media_file.mime_type,
        size_bytes=media_file.size_bytes,
        tag=media_file.tag,
        url=media_url,
        created_at=media_file.created_at,
    )


@router.get("/{media_id}", response_class=Response)
async def get_file(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """
    Получить файл по ID (требуется авторизация).
    
    Пользователь может получить только свои файлы, админы - любые.
    """
    media_repo = MediaRepository(db)
    media_file = await media_repo.get_by_id(media_id)
    
    if not media_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    user_role = current_user.get("role") if current_user else None
    user_id = current_user.get("id") if current_user else None
    
    if user_role != "admin" and media_file.uploaded_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    file_data_mime = await storage_service.get_file(media_file.s3_key)
    if not file_data_mime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage"
        )
    
    file_data, mime_type = file_data_mime
    
    safe_filename = media_file.original_filename.encode('ascii', 'ignore').decode('ascii')
    if not safe_filename:
        safe_filename = "file"
    if media_file.original_filename != safe_filename:
        encoded_filename = quote(media_file.original_filename, safe='')
        content_disposition = f'inline; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}'
    else:
        content_disposition = f'inline; filename="{safe_filename}"'
    
    return Response(
        content=file_data,
        media_type=mime_type,
        headers={
            "Content-Disposition": content_disposition,
            "Content-Length": str(len(file_data)),
        }
    )


@router.get("/{media_id}/info", response_model=MediaInfoResponse)
async def get_file_info(
    media_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Получить метаданные файла (требуется авторизация).
    
    Пользователь может получить только свои файлы, админы - любые.
    """
    media_repo = MediaRepository(db)
    media_file = await media_repo.get_by_id(media_id)
    
    if not media_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    user_role = current_user.get("role")
    user_id = current_user.get("id")
    if user_role != "admin" and media_file.uploaded_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    if settings.MEDIA_BASE_URL:
        media_url = f"{settings.MEDIA_BASE_URL}{settings.API_V1_PREFIX}/media/{media_file.id}"
    elif request:
        base_url = str(request.base_url).rstrip("/")
        media_url = f"{base_url}{settings.API_V1_PREFIX}/media/{media_file.id}"
    else:
        media_url = f"{settings.API_V1_PREFIX}/media/{media_file.id}"
    
    return MediaInfoResponse(
        id=media_file.id,
        filename=media_file.filename,
        original_filename=media_file.original_filename,
        mime_type=media_file.mime_type,
        size_bytes=media_file.size_bytes,
        uploaded_by=media_file.uploaded_by,
        tag=media_file.tag,
        url=media_url,
        created_at=media_file.created_at,
        updated_at=media_file.updated_at,
    )


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Удалить файл (требуется авторизация).
    
    Пользователь может удалить только свои файлы, админы - любые.
    """
    media_repo = MediaRepository(db)
    media_file = await media_repo.get_by_id(media_id)
    
    if not media_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    user_role = current_user.get("role")
    user_id = current_user.get("id")
    if user_role != "admin" and media_file.uploaded_by != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    await storage_service.delete_file(media_file.s3_key)
    await media_repo.delete_media_file(media_id)
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

