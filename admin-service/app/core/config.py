from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Project
    PROJECT_NAME: str = "Taxi Admin Service"
    VERSION: str = "1.0.0"
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    ROOT_PATH: str = "/admin"  # Префикс для работы за Nginx прокси
    
    # Auth Service
    AUTH_SERVICE_URL: str = Field(
        default="http://auth-service:8000",
        description="URL auth-service для проверки токенов"
    )
    
    # Driver Service
    DRIVER_SERVICE_URL: str = Field(
        default="http://driver-service:8001",
        description="URL driver-service"
    )
    
    # Order Service
    ORDER_SERVICE_URL: str = Field(
        default="http://order-service:8002",
        description="URL order-service"
    )
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
