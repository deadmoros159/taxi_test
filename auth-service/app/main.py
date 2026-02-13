from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
import structlog
import subprocess
import sys
import os
import re

from app.api.v1.endpoints import auth, users
from app.core.config import settings
from app.core.database import engine, Base, check_db_connection
from app.services.sms_service import sms_service
from app.utils.rate_limiter import rate_limiter

# Настройка структурированного логирования
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer() if settings.JSON_LOGS else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def run_migrations():
    """Запуск миграций Alembic"""
    try:
        logger.info("Running database migrations...")
        # Определяем путь к корню проекта (где находится alembic.ini)
        # app/main.py -> app -> auth-service
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(current_file))
        
        # Запускаем alembic upgrade head
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
            env=os.environ.copy()  # Передаем переменные окружения
        )
        if result.returncode == 0:
            logger.info("Database migrations completed successfully")
            if result.stdout:
                logger.debug("Migration output", output=result.stdout)
        else:
            # Проверяем, не связана ли ошибка с уже существующими объектами
            error_text = result.stderr.lower() if result.stderr else ""
            if "already exists" in error_text or "duplicate" in error_text:
                logger.warning(
                    "Migration objects already exist, skipping",
                    stderr=result.stderr
                )
                # Это не критично - объекты уже созданы
            else:
                logger.error(
                    "Migration failed",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    returncode=result.returncode
                )
                # В production это критическая ошибка только если не "already exists"
                if settings.ENVIRONMENT != "development":
                    raise RuntimeError(f"Migration failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("Migration timeout - migrations took too long")
        if settings.ENVIRONMENT != "development":
            raise
    except FileNotFoundError:
        logger.warning("Alembic not found, skipping migrations. Make sure alembic is installed.")
    except Exception as e:
        logger.error(f"Error running migrations: {e}", exc_info=True)
        if settings.ENVIRONMENT != "development":
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan для управления ресурсами"""
    # Startup
    logger.info("Starting Auth Service", version=settings.VERSION, env=settings.ENVIRONMENT)

    # Проверяем подключения
    db_ok = await check_db_connection()
    if not db_ok:
        logger.error("Failed to connect to database")
        if settings.ENVIRONMENT != "development":
            raise RuntimeError("Database connection failed")

    # Запускаем миграции
    # В production миграции обязательны
    # В development можно использовать create_all или миграции (через RUN_MIGRATIONS=true)
    if settings.ENVIRONMENT != "development":
        # В production/staging всегда запускаем миграции
        await run_migrations()
    elif os.getenv("RUN_MIGRATIONS", "false").lower() == "true":
        # В development можно включить миграции через переменную окружения
        await run_migrations()
    else:
        # В development по умолчанию используем create_all для быстрого старта
        logger.info("Development mode: creating tables from models")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            logger.warning(f"Failed to create tables from models: {e}. Run migrations manually.")

    # Инициализируем сервисы
    try:
        await sms_service.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize SMS service: {e}")
        if not settings.DEBUG:
            raise  # В production это критическая ошибка
    
    try:
        await rate_limiter.initialize()
    except Exception as e:
        logger.warning(f"Failed to initialize rate limiter: {e}. Continuing without rate limiting.")

    logger.info("Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Auth Service")


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
# Если CORS_ORIGINS содержит "*", то allow_credentials должен быть False
# Иначе используем список origins с allow_credentials=True
cors_origins = list(settings.CORS_ORIGINS) if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
cors_allow_credentials = settings.CORS_ALLOW_CREDENTIALS

# Добавляем поддержку всех localhost портов для разработки через regex
# allow_origin_regex принимает строку с регулярным выражением (не список!)
# Объединяем несколько паттернов через | (или)
localhost_regex = r"http://(localhost|127\.0\.0\.1):\d+"

# Если origins содержит "*", отключаем credentials (браузеры блокируют это сочетание)
if "*" in cors_origins:
    cors_allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=localhost_regex,  # Поддержка localhost с любым портом
    allow_credentials=cors_allow_credentials,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
    expose_headers=["X-Correlation-ID", "X-Request-ID"],
)


# Middleware для correlation ID и логирования запросов
@app.middleware("http")
async def correlation_and_logging_middleware(request: Request, call_next):
    start_time = time.time()

    # Пропускаем health checks из логирования
    if request.url.path == "/health":
        response = await call_next(request)
        return response

    # Correlation ID
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        import uuid
        correlation_id = str(uuid.uuid4())
    
    request_id = request.headers.get("X-Request-ID", correlation_id)

    logger.info(
        "Request started",
        request_id=request_id,
        correlation_id=correlation_id,
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host,
    )

    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        
        # Добавляем correlation ID в заголовки ответа
        response.headers["X-Correlation-ID"] = correlation_id

        logger.info(
            "Request completed",
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            duration=f"{process_time:.2f}ms",
        )

        return response
    except Exception as exc:
        process_time = (time.time() - start_time) * 1000

        logger.error(
            "Request failed",
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            url=str(request.url),
            error=str(exc),
            duration=f"{process_time:.2f}ms",
        )
        raise


# Обработчик ошибок
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        url=str(request.url),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        error=str(exc),
        url=str(request.url),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Подключаем роутеры
# Основные роутеры авторизации
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth")

# Методы авторизации
app.include_router(auth.phone_router, prefix=f"{settings.API_V1_PREFIX}/auth/phone", tags=["Phone Authentication"])
app.include_router(auth.email_router, prefix=f"{settings.API_V1_PREFIX}/auth/email", tags=["Email Authentication"])
app.include_router(auth.telegram_router, prefix=f"{settings.API_V1_PREFIX}/auth/telegram", tags=["Telegram Authentication"])
app.include_router(auth.admin_router, prefix=f"{settings.API_V1_PREFIX}/auth/admin", tags=["Admin Authentication"])

# Управление пользователями и сотрудниками
app.include_router(users.staff_router, prefix=f"{settings.API_V1_PREFIX}/users")
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check для Kubernetes и load balancers"""
    db_ok = await check_db_connection()

    if not db_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "unavailable"}
        )

    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected",
    }


@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs" if settings.DEBUG else None,
        "health": "/health",
    }