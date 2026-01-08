from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Admin Service"
    VERSION: str = "1.0.0"

    # External Services
    AUTH_SERVICE_URL: str = Field(
        default="http://auth-service:8000",
        description="URL auth-service"
    )
    DRIVER_SERVICE_URL: str = Field(
        default="http://driver-service:8001",
        description="URL driver-service"
    )
    ORDER_SERVICE_URL: str = Field(
        default="http://order-service:8002",
        description="URL order-service"
    )
    
    # Cache settings
    CACHE_TTL: int = 300  # 5 минут кэш для статистики

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

