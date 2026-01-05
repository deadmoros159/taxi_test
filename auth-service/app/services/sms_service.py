import logging
import time
from typing import Optional, Tuple
from app.core.config import settings
from app.services.firebase_service import firebase_sms_service
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SMSService:
    """
    Универсальный SMS сервис
    Использует Firebase для отправки, Redis для хранения сессий
    """

    def __init__(self):
        self.redis = None
        self.provider = settings.SMS_PROVIDER

    async def initialize(self):
        """Инициализация Redis"""
        if not self.redis:
            try:
                redis_url = str(settings.REDIS_URL)
                # Логируем только хост и порт для безопасности
                safe_url = redis_url.split('@')[-1] if '@' in redis_url else redis_url
                logger.info(f"Connecting to Redis: {safe_url}")
                
                # Используем URL напрямую, пароль уже должен быть в URL
                self.redis = redis.from_url(
                    redis_url,
                decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # Тестируем подключение
                await self.redis.ping()
                logger.info("SMS Service Redis connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Redis in SMS service: {e}", exc_info=True)
                # В DEBUG режиме можно продолжить без Redis (для разработки)
                if settings.DEBUG:
                    logger.warning("Continuing without Redis in DEBUG mode")
                    self.redis = None
                else:
                    # Redis критичен для SMS, поэтому поднимаем ошибку
                    raise

    async def send_sms(self, phone_number: str) -> Tuple[bool, Optional[str]]:
        """
        Отправка SMS кода

        Возвращает: (success, session_key для верификации)
        """
        await self.initialize()

        if self.provider == "firebase":
            # Используем Firebase для отправки SMS
            success, session_info = await firebase_sms_service.send_verification_code(phone_number)

            if success and session_info:
                # Сохраняем сессию в Redis (если доступен)
                if self.redis:
                    session_key = f"sms_session:{phone_number}"
                    try:
                        await self.redis.setex(
                            session_key,
                            settings.SMS_CODE_EXPIRE_SECONDS,
                            session_info
                        )
                        return True, session_key
                    except Exception as e:
                        logger.error(f"Failed to save session to Redis: {e}")
                        # Продолжаем без Redis, возвращаем session_info напрямую
                        return True, session_info
                else:
                    # Redis недоступен, возвращаем session_info напрямую
                    return True, session_info

            return False, None

        elif self.provider == "mock":
            # Для разработки
            logger.info(f"MOCK SMS sent to {phone_number}")
            mock_session = f"mock_session_{phone_number}_{int(time.time())}"

            session_key = f"sms_session:{phone_number}"
            if self.redis:
                try:
                    await self.redis.setex(
                        session_key,
                        settings.SMS_CODE_EXPIRE_SECONDS,
                        mock_session
                    )

                    # Сохраняем и код для моковой проверки
                    mock_code = "123456"  # Для тестов
                    code_key = f"sms_code:{phone_number}"
                    await self.redis.setex(
                        code_key,
                        settings.SMS_CODE_EXPIRE_SECONDS,
                        mock_code
                    )
                except Exception as e:
                    logger.warning(f"Redis unavailable in mock mode: {e}")

            return True, session_key

        else:
            logger.error(f"Unknown SMS provider: {self.provider}")
            return False, None

    async def verify_code(self, phone_number: str, code: str) -> Tuple[bool, Optional[dict]]:
        """
        Проверка SMS кода

        Возвращает: (success, user_data)
        """
        await self.initialize()

        # Получаем сессию из Redis (если доступен)
        session_info = None
        if self.redis:
            session_key = f"sms_session:{phone_number}"
            try:
                session_info = await self.redis.get(session_key)
            except Exception as e:
                logger.error(f"Failed to get session from Redis: {e}")

        # Если Redis недоступен или сессия не найдена, используем session_info из параметра
        # (для Firebase session_info передается напрямую)
        if not session_info:
            logger.warning(f"No session found in Redis for {phone_number}, trying direct verification")

        if self.provider == "firebase":
            # Проверяем код через Firebase (передаем номер для проверки тестовых номеров)
            success, user_data = await firebase_sms_service.verify_code(session_info, code, phone_number)

            if success:
                # Очищаем сессию
                await self.redis.delete(session_key)

                # Firebase вернет данные пользователя
                return True, user_data

            return False, None

        elif self.provider == "mock":
            # Моковая проверка
            if self.redis:
                code_key = f"sms_code:{phone_number}"
                try:
                    stored_code = await self.redis.get(code_key)

                    if stored_code and stored_code == code:
                        # Очищаем
                        await self.redis.delete(session_key)
                        await self.redis.delete(code_key)

                        # Возвращаем моковые данные
                        return True, {
                            "phone_number": phone_number,
                            "firebase_uid": f"mock_uid_{phone_number}",
                            "is_new_user": True
                        }
                except Exception as e:
                    logger.warning(f"Redis unavailable in mock verification: {e}")
            
            # Если Redis недоступен, проверяем код напрямую (для разработки)
            if code == "123456":
                return True, {
                    "phone_number": phone_number,
                    "firebase_uid": f"mock_uid_{phone_number}",
                    "is_new_user": True
                }

            return False, None

        return False, None

    async def cleanup(self, phone_number: str):
        """Очистка данных"""
        await self.initialize()

        session_key = f"sms_session:{phone_number}"
        code_key = f"sms_code:{phone_number}"

        await self.redis.delete(session_key)
        await self.redis.delete(code_key)


# Глобальный инстанс
sms_service = SMSService()