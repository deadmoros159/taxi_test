from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, field_validator
from typing import Optional

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Media Service"
    VERSION: str = "1.0.0"
    ROOT_PATH: str = ""  # Префикс пути для работы за прокси

    # Database
    POSTGRES_SERVER: str = Field(default="localhost", description="PostgreSQL server hostname")
    POSTGRES_USER: str = Field(default="postgres", description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(default="postgres", description="PostgreSQL password")
    POSTGRES_DB: str = Field(default="media_db", description="PostgreSQL database name")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL port")
    DATABASE_URL: Optional[PostgresDsn] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info):
        if isinstance(v, str):
            return v
        if not info.data.get("POSTGRES_SERVER"):
            return None
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=info.data.get("POSTGRES_SERVER"),
            port=info.data.get("POSTGRES_PORT", 5432),
            path=info.data.get("POSTGRES_DB", ""),
        )

    # Auth Service Integration
    AUTH_SERVICE_URL: str = Field(
        default="http://auth-service:8000",
        description="URL auth-service для проверки токенов"
    )

    # MinIO (S3-compatible) Configuration
    MINIO_ENDPOINT: str = Field(
        default="minio:9000",
        description="MinIO endpoint (host:port)"
    )
    MINIO_ACCESS_KEY: str = Field(
        default="minioadmin",
        description="MinIO access key"
    )
    MINIO_SECRET_KEY: str = Field(
        default="minioadmin",
        description="MinIO secret key"
    )
    MINIO_BUCKET_NAME: str = Field(
        default="media",
        description="MinIO bucket name for storing files"
    )
    MINIO_SECURE: bool = Field(
        default=False,
        description="Use HTTPS for MinIO (set to True in production with SSL)"
    )

    # File Upload Settings
    MAX_FILE_SIZE_MB: int = Field(
        default=5,
        description="Maximum file size in megabytes"
    )
    ALLOWED_MIME_TYPES: list[str] = Field(
        default=[
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        description="Allowed MIME types for upload"
    )
    
    # Media URL Settings
    MEDIA_BASE_URL: str = Field(
        default="",
        description="Base URL for media files (e.g., https://xhap.ru/media). If empty, will be generated from request."
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

