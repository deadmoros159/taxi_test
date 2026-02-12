from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import structlog
import re
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine, Base, check_db_connection
from app.api.v1.endpoints import router as media_router
from app.models.media import MediaTag

# Настройка логирования
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() if settings.DEBUG else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan для управления ресурсами"""
    # Startup
    logger.info("Starting Media Service", version=settings.VERSION, env=settings.ENVIRONMENT)

    # Создаем таблицы из моделей
    logger.info("Creating database tables from models")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Без Alembic: гарантируем наличие колонки tag + индекса
            await conn.execute(
                text(
                    "ALTER TABLE media_files "
                    "ADD COLUMN IF NOT EXISTS tag VARCHAR(32) NOT NULL DEFAULT :default_tag"
                ),
                {"default_tag": MediaTag.DOCUMENT.value},
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_media_files_tag ON media_files (tag)")
            )
        logger.info("Database tables created successfully")
    except Exception as e:
        error_str = str(e).lower()
        if "already exists" in error_str or "duplicate" in error_str:
            logger.info("Database objects already exist, skipping creation")
        else:
            logger.warning(f"Failed to create tables from models: {e}")
            if settings.ENVIRONMENT != "development":
                logger.error("Failed to create tables in production mode")

    # Проверяем подключения с повторными попытками (для Docker сети)
    logger.info("Checking database connection (with retries)...")
    db_ok = await check_db_connection(max_retries=10, retry_delay=3)
    if not db_ok:
        logger.error("Failed to connect to database after all retries")
        if settings.ENVIRONMENT != "development":
            raise RuntimeError("Database connection failed")

    # Инициализируем хранилище (создаем bucket если нужно)
    try:
        from app.services.storage_service import storage_service
        storage_service.ensure_bucket_exists()
        logger.info("Storage service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize storage service: {e}")
        if settings.ENVIRONMENT != "development":
            raise RuntimeError("Storage service initialization failed")

    logger.info("Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Media Service")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    root_path=settings.ROOT_PATH,
    lifespan=lifespan,
)

# Middleware - CORS
cors_origins = list(settings.CORS_ORIGINS) if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
cors_allow_credentials = settings.CORS_ALLOW_CREDENTIALS

# Добавляем поддержку всех localhost портов для разработки через regex
localhost_regex = [
    re.compile(r"http://localhost:\d+"),
    re.compile(r"http://127\.0\.0\.1:\d+"),
]

if "*" in cors_origins:
    cors_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=localhost_regex,  # Поддержка localhost с любым портом
    allow_credentials=cors_allow_credentials,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
    expose_headers=["X-Correlation-ID"],
)

# Подключаем роутеры
app.include_router(media_router, prefix=f"{settings.API_V1_PREFIX}/media", tags=["media"])


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check для Kubernetes и load balancers"""
    try:
        db_ok = await check_db_connection()
        
        if not db_ok:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "database": "unavailable"
                }
            )

        return {
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "database": "connected",
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/health",
    }

