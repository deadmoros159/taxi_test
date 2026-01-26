from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, RedisDsn, field_validator, SecretStr
from typing import Optional, Literal, List
import secrets


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Taxi Auth Service"
    VERSION: str = "1.0.0"
    ROOT_PATH: str = ""  # Префикс пути для работы за прокси (например, /auth)

    # Security
    SECRET_KEY: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)),
        description="Секретный ключ приложения"
    )
    JWT_SECRET_KEY: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)),
        description="Секретный ключ для JWT access токенов"
    )
    JWT_REFRESH_SECRET_KEY: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)),
        description="Секретный ключ для JWT refresh токенов"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 час
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: SecretStr = Field(
        default=SecretStr("postgres"),
        description="Пароль PostgreSQL"
    )
    POSTGRES_DB: str = "auth_db"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: Optional[PostgresDsn] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info):
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD").get_secret_value(),
            host=info.data.get("POSTGRES_SERVER"),
            port=info.data.get("POSTGRES_PORT", 5432),
            path=f"{info.data.get('POSTGRES_DB') or ''}",
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[SecretStr] = None
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_URL: Optional[RedisDsn] = None

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info):
        if isinstance(v, str):
            return v

        password = info.data.get("REDIS_PASSWORD")
        password_str = password.get_secret_value() if password else None
        host = info.data.get("REDIS_HOST", "localhost")
        port = info.data.get("REDIS_PORT", 6379)
        db = info.data.get("REDIS_DB", 0)

        # Формируем URL вручную с правильным экранированием пароля
        # Если пароль не установлен, используем URL без пароля
        from urllib.parse import quote_plus
        if password_str:
            # Экранируем пароль для URL (все специальные символы)
            encoded_password = quote_plus(password_str, safe='')
            return f"redis://:{encoded_password}@{host}:{port}/{db}"
        else:
            return f"redis://{host}:{port}/{db}"

    # Firebase Configuration
    FIREBASE_API_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="Firebase Web API Key (начинается с AIzaSy...)"
    )
    FIREBASE_PROJECT_ID: str = Field(
        default="",
        description="Firebase Project ID"
    )
    FIREBASE_AUTH_DOMAIN: Optional[str] = None
    FIREBASE_STORAGE_BUCKET: Optional[str] = None
    FIREBASE_MESSAGING_SENDER_ID: Optional[str] = None
    FIREBASE_APP_ID: Optional[str] = None

    # SMS Configuration
    SMS_PROVIDER: Literal["firebase", "mock", "twilio", "smsru"] = "mock"
    SMS_CODE_EXPIRE_SECONDS: int = 300  # 5 минут
    SMS_CODE_LENGTH: int = 6
    SMS_MAX_ATTEMPTS: int = 5
    SMS_COOLDOWN_SECONDS: int = 60  # Задержка между отправкой SMS

    # Email Configuration
    SMTP_SERVER: str = Field(default="", description="SMTP сервер для отправки email")
    SMTP_PORT: int = Field(default=465, description="SMTP порт (465 для SSL, 587 для STARTTLS)")
    SMTP_USERNAME: str = Field(default="", description="Имя пользователя SMTP")
    SMTP_PASSWORD: SecretStr = Field(default=SecretStr(""), description="Пароль от SMTP аккаунта")
    SENDER_EMAIL: str = Field(default="", description="Email отправителя")
    SMTP_SSL_CERT_PATH: Optional[str] = Field(default=None, description="Путь к SSL сертификату (если не указан, используется самоподписанный)")
    EMAIL_CODE_EXPIRE_SECONDS: int = 300  # 5 минут
    EMAIL_CODE_LENGTH: int = 6
    EMAIL_MAX_ATTEMPTS: int = 5
    EMAIL_COOLDOWN_SECONDS: int = 60  # Задержка между отправкой email
    
    # Firebase Test Phone Numbers (для разработки без биллинга)
    # Формат: "+998901234567:123456" (номер:код)
    # Можно задать через переменную окружения как JSON массив: ["+998901234567:123456"]
    # Или через запятую: "+998901234567:123456,+998901234568:654321"
    FIREBASE_TEST_PHONES: Optional[List[str]] = Field(
        default_factory=list,
        description="Список тестовых номеров Firebase в формате 'номер:код'"
    )

    # Для других SMS провайдеров
    SMS_API_KEY: Optional[SecretStr] = None
    SMS_API_SECRET: Optional[SecretStr] = None
    SMS_FROM_NUMBER: Optional[str] = None

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_PER_HOUR: int = 100
    RATE_LIMIT_SMS_PER_DAY: int = 5

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Разрешенные origins для CORS"
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    JSON_LOGS: bool = False
    LOG_FILE: Optional[str] = "auth_service.log"

    # Health checks
    HEALTH_CHECK_TIMEOUT: int = 5

    # Phone number validation
    ALLOWED_PHONE_PREFIXES: List[str] = Field(
        default=["+998", "+7"],
        description="Разрешенные префиксы номеров телефонов"
    )
    
    # External Services
    DRIVER_SERVICE_URL: str = Field(
        default="http://driver-service:8001",
        description="URL driver-service для получения данных водителя"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Игнорировать лишние переменные


settings = Settings()