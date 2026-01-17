from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import redis.asyncio as redis
import asyncio
from datetime import datetime
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self):
        self.redis = None
        self._lock = asyncio.Lock()

    async def initialize(self):
        if not self.redis:
            try:
                redis_url = str(settings.REDIS_URL)

                # Используем URL напрямую, пароль уже должен быть в URL
                self.redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5.0,  # Таймаут подключения 5 секунд
                    socket_timeout=5.0,  # Таймаут операций 5 секунд
                )
                # Тестируем подключение с таймаутом
                await asyncio.wait_for(self.redis.ping(), timeout=10.0)  # Общий таймаут 10 секунд
                logger.info("Redis connection established")
            except (asyncio.TimeoutError, TimeoutError):
                logger.error("Redis connection timeout")
                self.redis = None
                if not settings.DEBUG:
                    raise RuntimeError("Redis connection timeout")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                # В development режиме можно продолжить без Redis
                if settings.DEBUG:
                    logger.warning("Continuing without Redis in DEBUG mode")
                    self.redis = None
                else:
                    raise

    async def is_rate_limited(self, key: str, limit: int, period: int) -> bool:
        """Проверка превышения лимита запросов"""
        await self.initialize()

        # Если Redis недоступен, пропускаем rate limiting в DEBUG режиме
        if not self.redis:
            return False

        try:
            current_time = datetime.now()  # ← ИСПРАВЛЕНО: добавлен отступ
            current_minute = current_time.strftime("%Y%m%d%H%M")

            redis_key = f"rate_limit:{key}:{current_minute}"

            # Атомарное увеличение счетчика
            count = await self.redis.incr(redis_key)
            if count == 1:
                await self.redis.expire(redis_key, period)

            return count > limit
        except Exception as e:
            logger.error(f"Redis error in rate limiting: {e}")
            # В случае ошибки Redis, пропускаем rate limiting
            return False

    async def check_request_limit(self, request: Request, identifier: str = None):
        """Проверка лимита запросов для endpoint"""
        if settings.DEBUG:
            return

        identifier = identifier or request.client.host

        # Проверка по минутам
        if await self.is_rate_limited(
                f"{identifier}:minute",
                settings.RATE_LIMIT_PER_MINUTE,
                60
        ):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )

        # Проверка по часам
        if await self.is_rate_limited(
                f"{identifier}:hour",
                settings.RATE_LIMIT_PER_HOUR,
                3600
        ):
            raise HTTPException(
                status_code=429,
                detail="Hourly request limit exceeded."
            )


rate_limiter = RateLimiter()