"""
Сервис для одноразовых кодов авторизации через Telegram.
Код хранится в Redis (TTL 5 мин), обменивается на access_token + refresh_token.
"""
import json
import secrets
import logging

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

CODE_TTL = 300  # 5 минут
REDIS_PREFIX = "tg_auth_code:"


class TelegramAuthCodeService:
    def __init__(self):
        self.redis = None

    async def _get_redis(self):
        if self.redis is None:
            try:
                redis_url = str(settings.REDIS_URL)
                self.redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5.0,
                    socket_timeout=5.0,
                )
                await self.redis.ping()
            except Exception as e:
                logger.error(f"Redis connection failed for telegram auth codes: {e}")
                raise
        return self.redis

    async def create_code(self, access_token: str, refresh_token: str) -> str:
        """Создать одноразовый код, хранить токены в Redis."""
        r = await self._get_redis()
        code = secrets.token_urlsafe(12)
        key = f"{REDIS_PREFIX}{code}"
        value = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
        await r.setex(key, CODE_TTL, value)
        return code

    async def exchange_code(self, code: str) -> tuple[str, str] | None:
        """Обменять код на токены. Код одноразовый — после обмена удаляется."""
        if not code or not code.strip():
            return None
        r = await self._get_redis()
        key = f"{REDIS_PREFIX}{code.strip()}"
        value = await r.get(key)
        if not value:
            return None
        await r.delete(key)
        try:
            data = json.loads(value)
            return data["access_token"], data["refresh_token"]
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid telegram auth code data: {e}")
            return None


telegram_auth_code_service = TelegramAuthCodeService()
