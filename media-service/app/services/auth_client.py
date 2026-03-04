import httpx
import logging
from typing import Optional, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthClient:
    def __init__(self):
        self.base_url = settings.AUTH_SERVICE_URL
        self.client = httpx.AsyncClient(
            timeout=5.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            follow_redirects=True,
        )

    async def verify_token(self, token: str) -> Optional[Dict]:
        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Token verification failed: {response.status_code}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Error verifying token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error verifying token: {e}", exc_info=True)
            return None

    async def close(self):
        await self.client.aclose()

