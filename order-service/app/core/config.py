from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, field_validator
from typing import Optional

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
    
    # Order Settings
    DRIVER_COMMISSION_PERCENT: float = 20.0  # 20% комиссия с каждого заказа
    DEBT_CHECK_INTERVAL_DAYS: int = 7  # Проверка долга каждую неделю
    
    # Pricing Settings
    BASE_FARE: float = 50.0  # Базовая стоимость поездки (руб)
    PRICE_PER_KM: float = 15.0  # Стоимость за километр (руб/км)
    PRICE_PER_MINUTE: float = 2.0  # Стоимость за минуту (руб/мин)
    MINIMUM_FARE: float = 100.0  # Минимальная стоимость поездки (руб)
    
    # WebSocket Settings
    WS_HEARTBEAT_INTERVAL: int = 30  # Интервал heartbeat в секундах

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()


