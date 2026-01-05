from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

import sys
import os

# Добавляем shared library в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../shared'))

from app.core.config import settings
from app.api.v1.endpoints import drivers
from app.services.auth_client import auth_client
from correlation import set_correlation_id, get_correlation_id

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan для управления ресурсами"""
    # Startup
    logger.info("Starting Driver Service", version=settings.VERSION)
    yield
    
    # Shutdown
    logger.info("Shutting down Driver Service")
    await auth_client.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

