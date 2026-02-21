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
cors_origins = list(settings.CORS_ORIGINS) if isinstance(settings.CORS_ORIGINS, list) else [str(settings.CORS_ORIGINS)]
cors_allow_credentials = settings.CORS_ALLOW_CREDENTIALS
allow_methods = list(settings.CORS_ALLOW_METHODS) if isinstance(settings.CORS_ALLOW_METHODS, (list, tuple)) else ["*"]
allow_headers = list(settings.CORS_ALLOW_HEADERS) if isinstance(settings.CORS_ALLOW_HEADERS, (list, tuple)) else ["*"]

if "*" in cors_origins:
    cors_allow_credentials = False

# allow_origin_regex — только str, только в development (избегаем TypeError в production)
cors_kwargs = dict(
    allow_origins=cors_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=allow_methods,
    allow_headers=allow_headers,
    expose_headers=["X-Correlation-ID"],
)
if settings.ENVIRONMENT == "development":
    cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1):\d+"

app.add_middleware(CORSMiddleware, **cors_kwargs)

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


