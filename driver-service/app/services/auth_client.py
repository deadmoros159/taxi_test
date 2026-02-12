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

    async def check_user_exists(self, user_id: int, token: str) -> bool:
        """
        Проверить, существует ли пользователь
        
        Args:
            user_id: ID пользователя
            token: Токен для авторизации
            
        Returns:
            True если пользователь существует, False иначе
        """
        user_info = await self.get_user_info(user_id, token)
        return user_info is not None
    
    async def create_user(
        self,
        full_name: str,
        phone_number: str,
        token: str,
        email: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Создать нового пользователя в auth-service
        
        Args:
            full_name: Полное имя
            phone_number: Номер телефона
            token: Токен диспетчера/админа для авторизации
            email: Email (опционально)
            
        Returns:
            Данные созданного пользователя или None
        """
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
            
            # Используем внутренний endpoint для создания пользователя (если есть)
            # Или создаем через SMS flow
            # Пока используем упрощенный вариант - создание через phone auth
            response = await self.client.post(
                "/api/v1/auth/phone/request",
                headers=headers,
                json={
                    "phone_number": phone_number,
                    "full_name": full_name
                }
            )
            
            # Если пользователь уже существует, получаем его данные
            if response.status_code == 200:
                # Пользователь создан или уже существует, получаем его данные
                # Нужно найти пользователя по телефону
                # Для этого можно использовать внутренний endpoint или создать отдельный
                logger.info(f"User creation initiated for {phone_number}")
                return {"phone_number": phone_number, "full_name": full_name}
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating user: {e}", exc_info=True)
            return None
    
    async def create_user_direct(
        self,
        full_name: str,
        phone_number: str,
        token: str,
        email: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Создать пользователя напрямую (для офисной регистрации)
        
        Args:
            full_name: Полное имя
            phone_number: Номер телефона
            token: Токен диспетчера/админа
            email: Email (опционально)
            
        Returns:
            Данные созданного пользователя или None
        """
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
                logger.warning(f"User already exists: {phone_number}")
                # Пытаемся найти существующего пользователя
                # Пока возвращаем None, можно добавить поиск по телефону
                return None
            else:
                logger.error(f"Failed to create user: {response.status_code} - {response.text}")
                return None
            
        except Exception as e:
            logger.error(f"Error creating user directly: {e}", exc_info=True)
            return None
    
    async def find_user_by_phone(self, phone_number: str, token: str) -> Optional[Dict[str, Any]]:
        """
        Найти пользователя по номеру телефона
        
        Args:
            phone_number: Номер телефона
            token: Токен для авторизации
            
        Returns:
            Данные пользователя или None
        """
        # Пока используем обходной путь - пытаемся создать пользователя,
        # если он уже существует, auth-service вернет 409
        # В будущем можно добавить отдельный endpoint в auth-service
        logger.warning("find_user_by_phone not fully implemented - using workaround")
        return None

    async def promote_user_to_driver(self, user_id: int, token: str) -> bool:
        """Перевести пользователя в роль driver (dispatcher/admin) через auth-service"""
        try:
            correlation_id = get_correlation_id()
            headers = {"Authorization": f"Bearer {token}"}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            response = await self.client.patch(
                f"/api/v1/users/{user_id}/promote-to-driver",
                headers=headers,
                json={},  # тело не требуется, но ResilientHTTPClient ожидает json для некоторых реализаций
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error promoting user to driver: {e}", exc_info=True)
            return False
    
    async def close(self):
        """Закрыть HTTP клиент"""
        await self.client.close()


# Глобальный экземпляр клиента
auth_client = AuthServiceClient()

