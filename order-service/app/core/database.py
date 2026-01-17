from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.core.config import settings
import logging
import asyncio
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# Создаем базовый класс для моделей
Base = declarative_base()

# Создаем движок для асинхронных операций
# Уменьшаем pool_size для экономии памяти (были OOM kills)
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    pool_size=5,  # Уменьшено с 20 до 5
    max_overflow=10,  # Уменьшено с 40 до 10
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Создаем фабрику сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Проверка подключения к БД с таймаутом"""
    try:
        # Добавляем таймаут 5 секунд для проверки подключения
        async with AsyncSessionLocal() as session:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=5.0
            )
        return True
    except asyncio.TimeoutError:
        logger.error("Database connection timeout: не удалось подключиться за 5 секунд")
        return False
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return False


