import httpx
import logging
from typing import Optional, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthClient:
    """Клиент для работы с auth-service API"""

    def __init__(self):
        self.base_url = settings.AUTH_SERVICE_URL
        # Настройки клиента для лучшей работы в Docker сети
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            follow_redirects=True
        )

    async def authorize_via_telegram(
        self,
        phone_number: str,
        full_name: str,
        telegram_user_id: int,
        telegram_username: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Авторизация через Telegram (без SMS кода)

        Args:
            phone_number: Номер телефона из Telegram
            full_name: Имя пользователя из Telegram
            telegram_user_id: ID пользователя в Telegram
            telegram_username: Username в Telegram (опционально)

        Returns:
            Dict с токенами и данными пользователя или None при ошибке
        """
        try:
            url = f"{self.base_url}/api/v1/auth/telegram/authorize"
            logger.info(f"Attempting to authorize via Telegram, URL: {url}, base_url: {self.base_url}")

            payload = {
                "phone_number": phone_number,
                "full_name": full_name,
                "telegram_user_id": telegram_user_id,
                "telegram_username": telegram_username
            }

            logger.debug(f"Sending request to {url} with payload: {payload}")
            response = await self.client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Successfully authorized via Telegram: {phone_number}")
                return data
            else:
                error_data = response.json() if response.content else {}
                logger.error(
                    f"Auth service error: {response.status_code}, "
                    f"detail: {error_data.get('detail', 'Unknown error')}"
                )
                return None

        except httpx.TimeoutException as e:
            logger.error(f"Timeout connecting to auth-service: {self.base_url}, error: {e}")
            return None

    async def telegram_user_exists(self, telegram_user_id: int) -> Optional[Dict]:
        """Проверить наличие пользователя по telegram_user_id"""
        try:
            url = f"{self.base_url}/api/v1/auth/telegram/check/{telegram_user_id}"
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Error checking telegram user: {e}", exc_info=True)
            return None

    async def authorize_via_telegram_id(self, telegram_user_id: int) -> Optional[Dict]:
        """Авторизация по telegram_user_id (без контакта)"""
        try:
            url = f"{self.base_url}/api/v1/auth/telegram/authorize-by-id"
            payload = {"telegram_user_id": telegram_user_id}
            response = await self.client.post(url, json=payload)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            logger.error(f"Error authorizing via telegram id: {e}", exc_info=True)
            return None
        except httpx.ConnectError as e:
            logger.error(f"Connection error to auth-service: {self.base_url}, error: {e}, URL was: {url if 'url' in locals() else 'unknown'}")
            return None
        except Exception as e:
            logger.error(f"Error authorizing via Telegram: {e}, base_url: {self.base_url}, URL was: {url if 'url' in locals() else 'unknown'}", exc_info=True)
            return None

    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.aclose()

