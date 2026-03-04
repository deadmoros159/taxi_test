import sys
import os
import logging
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../shared'))

from http_client import ResilientHTTPClient
from correlation import get_correlation_id
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthServiceClient:
    def __init__(self):
        self.client = ResilientHTTPClient(
            base_url=settings.AUTH_SERVICE_URL,
            timeout=5.0
        )
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            correlation_id = get_correlation_id()
            headers = {
                "Authorization": f"Bearer {token}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
            
            response = await self.client.get(
                "/api/v1/users/me",
                headers=headers
            )
            
            if response.status_code == 200:
                user_data = response.json()
                logger.debug(f"Token verified for user {user_data.get('id')}")
                return user_data
            else:
                logger.warning(f"Token verification failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error verifying token: {e}", exc_info=True)
            return None
    
    async def get_user_info(self, user_id: int, token: str) -> Optional[Dict[str, Any]]:
        try:
            correlation_id = get_correlation_id()
            headers = {
                "Authorization": f"Bearer {token}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
            
            response = await self.client.get(
                f"/api/v1/users/{user_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception as e:
            logger.error(f"Error getting user info: {e}", exc_info=True)
            return None

    async def check_user_exists(self, user_id: int, token: str) -> bool:
        user_info = await self.get_user_info(user_id, token)
        return user_info is not None
    
    async def create_user_direct(
        self,
        full_name: str,
        phone_number: str,
        token: str,
        email: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            correlation_id = get_correlation_id()
            headers = {"Authorization": f"Bearer {token}"}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
            
            payload = {
                "full_name": full_name,
                "phone_number": phone_number
            }
            if email:
                payload["email"] = email
            
            response = await self.client.post(
                "/api/v1/users/create",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"User created directly: {user_data.get('id')} - {phone_number}")
                return user_data
            elif response.status_code == 409:
                return None
            else:
                logger.error(f"Failed to create user: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            logger.error(f"Error creating user directly: {e}", exc_info=True)
            return None
    
    async def promote_user_to_driver(self, user_id: int, token: str) -> bool:
        try:
            correlation_id = get_correlation_id()
            headers = {"Authorization": f"Bearer {token}"}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            response = await self.client.patch(
                f"/api/v1/users/{user_id}/promote-to-driver",
                headers=headers,
                json={}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error promoting user to driver: {e}", exc_info=True)
            return False
    
    async def close(self):
        await self.client.close()


auth_client = AuthServiceClient()

