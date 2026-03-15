from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, field_validator
from typing import Optional, List

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Order Service"
    VERSION: str = "1.0.0"
    ROOT_PATH: str = ""  # Префикс пути для работы за прокси (например, /order)

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "order_db"
    POSTGRES_PORT: int = 5432
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

    # External Services
    AUTH_SERVICE_URL: str = Field(
        default="http://auth-service:8000",
        description="URL auth-service для проверки токенов"
    )
    DRIVER_SERVICE_URL: str = Field(
        default="http://driver-service:8001",
        description="URL driver-service"
    )
    TELEGRAM_BOT_SERVICE_URL: str = Field(
        default="http://telegram-bot-service:8004",
        description="URL telegram-bot-service для уведомлений"
    )
    AUTH_INTERNAL_KEY: Optional[str] = Field(
        default=None,
        description="Ключ для вызова внутренних API auth-service (X-Internal-Key)"
    )
    
    # Order Settings
    DRIVER_COMMISSION_PERCENT: float = 20.0  # 20% комиссия с каждого заказа
    DEBT_CHECK_INTERVAL_DAYS: int = 7  # Проверка долга каждую неделю
    
    # Pricing Settings (Узбекистан — комфорт класс, ~3000 сом/км)
    CURRENCY: str = Field(default="UZS", description="Валюта (UZS = узбекский сом)")
    BASE_FARE: float = Field(default=5000.0, description="Базовая стоимость поездки (сом)")
    PRICE_PER_KM: float = Field(default=3000.0, description="Стоимость за километр (сом/км)")
    PRICE_PER_MINUTE: float = Field(default=100.0, description="Стоимость за минуту (сом/мин)")
    MINIMUM_FARE: float = Field(default=8000.0, description="Минимальная стоимость (сом)")

    # Routing (OSRM) — для точного расчёта расстояния по дорогам
    OSRM_URL: Optional[str] = Field(
        default="https://router.project-osrm.org",
        description="URL OSRM. Пусто — использовать haversine с коэффициентом"
    )
    OSRM_TIMEOUT: int = Field(default=5, description="Таймаут OSRM в секундах")
    HAVERSINE_MULTIPLIER: float = Field(
        default=1.25,
        description="Коэффициент к прямолинейному расстоянию, если OSRM недоступен (город ~1.2–1.3)"
    )
    
    # WebSocket Settings
    WS_HEARTBEAT_INTERVAL: int = 30  # Интервал heartbeat в секундах

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


