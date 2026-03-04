import httpx
import logging
from typing import Optional, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthClient:
    def __init__(self):
        self.base_url = settings.AUTH_SERVICE_URL
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
        telegram_username: Optional[str] = None,
        photo_id: Optional[int] = None,
        email: Optional[str] = None
    ) -> Optional[Dict]:
        try:
            url = f"{self.base_url}/api/v1/auth/telegram/authorize"
            logger.info(f"Attempting to authorize via Telegram, URL: {url}, base_url: {self.base_url}")

            payload = {
                "phone_number": phone_number,
                "full_name": full_name,
                "telegram_user_id": telegram_user_id,
                "telegram_username": telegram_username,
                "photo_id": photo_id,
                "email": email
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

    async def create_telegram_auth_code(
        self,
        *,
        telegram_user_id: Optional[int] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ) -> Optional[str]:
        try:
            url = f"{self.base_url}/api/v1/auth/telegram/create-auth-code"
            if telegram_user_id is not None:
                payload = {"telegram_user_id": telegram_user_id}
            elif access_token and refresh_token:
                payload = {"access_token": access_token, "refresh_token": refresh_token}
            else:
                return None
            response = await self.client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                return data.get("code")
            return None
        except Exception as e:
            logger.error(f"Error creating telegram auth code: {e}", exc_info=True)
            return None

    async def close(self):
        await self.client.aclose()

