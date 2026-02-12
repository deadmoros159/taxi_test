from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

import sys
import os
from sqlalchemy import text

# Добавляем shared library в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

from app.core.config import settings
from app.api.v1.endpoints import drivers
from app.services.auth_client import auth_client
from app.core.database import engine, Base
from correlation import set_correlation_id, get_correlation_id

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan для управления ресурсами"""
    # Startup
    logger.info("Starting Driver Service", version=settings.VERSION)
    # Создаем таблицы из моделей (без Alembic)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Добавляем новые колонки для media_id, если сервис уже в проде
            await conn.execute(text("ALTER TABLE drivers ADD COLUMN IF NOT EXISTS license_photo_media_id INTEGER"))
            await conn.execute(text("ALTER TABLE drivers ADD COLUMN IF NOT EXISTS passport_photo_media_id INTEGER"))
            await conn.execute(text("ALTER TABLE drivers ADD COLUMN IF NOT EXISTS driver_photo_media_id INTEGER"))
            await conn.execute(text("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS vehicle_photo_media_id INTEGER"))
    except Exception as e:
        logger.warning(f"DB init/alter failed (might be already applied): {e}")
    yield
    
    # Shutdown
    logger.info("Shutting down Driver Service")
    await auth_client.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    root_path=settings.ROOT_PATH,  # Префикс пути для работы за прокси
    lifespan=lifespan
)

# CORS
# Если CORS_ORIGINS содержит "*", то allow_credentials должен быть False
cors_origins = list(settings.CORS_ORIGINS) if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
cors_allow_credentials = settings.CORS_ALLOW_CREDENTIALS

# Добавляем поддержку всех localhost портов для разработки через regex
import re
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


# Middleware для correlation ID
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Добавляет correlation ID к каждому запросу"""
    correlation_id = request.headers.get("X-Correlation-ID")
    if correlation_id:
        set_correlation_id(correlation_id)
    else:
        set_correlation_id()
    
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = get_correlation_id() or ""
    return response


# Подключаем роутеры
app.include_router(drivers.router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "driver-service"}


@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs"
    }

