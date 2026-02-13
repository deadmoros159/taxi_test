from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import structlog
import re

from app.core.config import settings
from app.api.v1.endpoints import dashboard, database

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
    logger.info("Starting Admin Service", version=settings.VERSION, env=settings.ENVIRONMENT)
    
    logger.info("Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Admin Service")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    root_path=settings.ROOT_PATH,  # Префикс пути для работы за прокси
    lifespan=lifespan,
)

# Middleware - CORS
cors_origins = list(settings.CORS_ORIGINS) if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
cors_allow_credentials = settings.CORS_ALLOW_CREDENTIALS

# Добавляем поддержку всех localhost портов для разработки через regex
# allow_origin_regex принимает список строк (регулярных выражений), а не скомпилированные объекты
localhost_regex = [
    r"http://localhost:\d+",
    r"http://127\.0\.0\.1:\d+",
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
app.include_router(dashboard.router, prefix=f"{settings.API_V1_PREFIX}/admin", tags=["admin"])
app.include_router(database.router, prefix=f"{settings.API_V1_PREFIX}/db", tags=["database"])


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check для Kubernetes и load balancers"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/health",
    }


