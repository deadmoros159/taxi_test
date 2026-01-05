"""
Клиент для взаимодействия с auth-service
Использует Circuit Breaker и Retry Logic для надежности
"""
import sys
import os
import logging
from typing import Optional, Dict, Any

# Добавляем shared library в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../shared'))

from http_client import ResilientHTTPClient
from correlation import get_correlation_id
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthServiceClient:
    """
    Клиент для auth-service с защитой от сбоев
    
    Принципы:
    - Не изменяет данные напрямую (только чтение)
    - Использует Circuit Breaker для защиты
    - Retry с exponential backoff
    """
    
    def __init__(self):
        self.client = ResilientHTTPClient(
            base_url=settings.AUTH_SERVICE_URL,
            timeout=5.0
        )
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Проверить токен через auth-service
        
        Args:
            token: JWT токен
            
        Returns:
            Данные пользователя или None если токен невалидный
        """
        try:
            correlation_id = get_correlation_id()
            headers = {
                "Authorization": f"Bearer {token}"
            }
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id
            
            response = await self.client.get(
                "/api/v1/me",
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
        """
        Получить информацию о пользователе
        
        Args:
            user_id: ID пользователя
            token: Токен для авторизации
            
        Returns:
            Данные пользователя или None
        """
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
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.close()


# Глобальный экземпляр клиента
auth_client = AuthServiceClient()

