from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Создаем async engine
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Создаем session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Базовый класс для моделей
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency для получения DB сессии"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_connection(max_retries: int = 5, retry_delay: int = 2) -> bool:
    """Проверка подключения к БД с повторными попытками"""
    import asyncio
    from sqlalchemy import text
    
    for attempt in range(max_retries):
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
                logger.info(f"Database connection successful (attempt {attempt + 1}/{max_retries})")
                return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database connection check failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Database connection check failed after {max_retries} attempts: {e}")
                return False
    return False

