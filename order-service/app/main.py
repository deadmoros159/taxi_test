from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import structlog

from app.core.config import settings
from app.core.database import engine, Base, check_db_connection
from app.api.v1.endpoints import orders
from sqlalchemy import text

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
    logger.info("Starting Order Service", version=settings.VERSION, env=settings.ENVIRONMENT)

    # Создаем таблицы из моделей (проще и надежнее чем миграции для начала)
    logger.info("Creating database tables from models")
    try:
        # Сначала создаем enum, если его нет
        async with engine.begin() as conn:
            # Проверяем и создаем enum для статусов заказов
            await conn.execute(
                text("""
                DO $$ BEGIN
                    CREATE TYPE orderstatus AS ENUM ('pending', 'accepted', 'driver_arrived', 'in_progress', 'completed', 'cancelled', 'cancelled_by_driver', 'cancelled_by_passenger');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
                """)
            )
            # Затем создаем таблицы
            await conn.run_sync(Base.metadata.create_all)
            # Добавляем order_date для отложенных заказов (без Alembic)
            await conn.execute(
                text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_date TIMESTAMPTZ")
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_orders_order_date ON orders (order_date)")
            )
        logger.info("Database tables created successfully")
    except Exception as e:
        error_str = str(e).lower()
        # Игнорируем ошибки о существующих объектах
        if "already exists" in error_str or "duplicate" in error_str:
            logger.info("Database objects already exist, skipping creation")
        else:
            logger.warning(f"Failed to create tables from models: {e}")
            # Не падаем, возможно таблицы уже существуют
            if settings.ENVIRONMENT != "development":
                logger.error("Failed to create tables in production mode")
                # В production можно продолжить, если таблицы уже есть

    # Проверяем подключения
    db_ok = await check_db_connection()
    if not db_ok:
        logger.error("Failed to connect to database")
        if settings.ENVIRONMENT != "development":
            raise RuntimeError("Database connection failed")

    logger.info("Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Order Service")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    root_path=settings.ROOT_PATH,  # Префикс пути для работы за прокси
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(orders.router, prefix=f"{settings.API_V1_PREFIX}/orders")


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

