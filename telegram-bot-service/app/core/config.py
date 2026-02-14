from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr
from typing import Optional, List


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: SecretStr = Field(
        ...,
        description="Токен Telegram бота"
    )

    # Auth Service
    AUTH_SERVICE_URL: str = Field(
        default="http://auth-service:8000",
        description="URL auth-service для авторизации"
    )
    
    # Media Service
    MEDIA_SERVICE_URL: str = Field(
        default="http://media-service:8003",
        description="URL media-service для загрузки файлов"
    )

    # Webhook
    WEBHOOK_HOST: str = Field(
        default="http://localhost:8004",
        description="Публичный URL для webhook (должен быть доступен из интернета)"
    )
    WEBHOOK_PATH: str = Field(
        default="/webhook",
        description="Путь для webhook endpoint"
    )
    WEBHOOK_SECRET: Optional[SecretStr] = Field(
        default=None,
        description="Секретный ключ для webhook (опционально)"
    )

    # Server
    HOST: str = Field(default="0.0.0.0", description="Хост для FastAPI сервера")
    PORT: int = Field(default=8004, description="Порт для FastAPI сервера")

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "https://xhap.ru"],
        description="Разрешенные origins для CORS"
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

