import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from jose import JWTError, jwt
import uuid
from pydantic import SecretStr

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenService:
    """Сервис для работы с JWT токенами"""

    def __init__(self):
        # Получаем секретные ключи, конвертируя SecretStr в строку
        # Всегда используем get_secret_value, так как JWT_SECRET_KEY всегда SecretStr
        try:
            self.access_secret = settings.JWT_SECRET_KEY.get_secret_value()
        except (AttributeError, TypeError):
            # Fallback на str если get_secret_value недоступен
            self.access_secret = str(settings.JWT_SECRET_KEY)
        
        try:
            self.refresh_secret = settings.JWT_REFRESH_SECRET_KEY.get_secret_value()
        except (AttributeError, TypeError):
            # Fallback на str если get_secret_value недоступен
            self.refresh_secret = str(settings.JWT_REFRESH_SECRET_KEY)
        self.algorithm = settings.ALGORITHM
        self.access_token_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    def create_access_token(self, user_id: int, phone_number: str = None, full_name: str = None, role: str = None, email: str = None) -> str:
        """
        Создание access токена

        Args:
            user_id: ID пользователя
            phone_number: Номер телефона (опционально)
            full_name: Полное имя пользователя (опционально)
            role: Роль пользователя (опционально)
            email: Email адрес (опционально)

        Returns:
            Access токен в виде строки
        """
        try:
            expire_time = datetime.utcnow() + self.access_token_expire
            token_id = str(uuid.uuid4())

            # Базовые данные
            payload = {
                "sub": str(user_id),
                "type": "access",
                "exp": expire_time,
                "iat": datetime.utcnow(),
                "jti": token_id,
            }

            # Добавляем телефон если есть
            if phone_number:
                payload["phone"] = phone_number
            
            # Добавляем email если есть
            if email:
                payload["email"] = email

            # Добавляем имя если есть
            if full_name:
                payload["name"] = full_name
            
            # Добавляем роль если есть
            if role:
                payload["role"] = role

            # Создаем токен
            access_token = jwt.encode(
                payload,
                self.access_secret,
                algorithm=self.algorithm
            )

            logger.debug(f"Access token created for user {user_id}, expires: {expire_time}")
            return access_token

        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            raise

    def create_refresh_token(self, user_id: int) -> Tuple[str, str, datetime]:
        """
        Создание refresh токена

        Args:
            user_id: ID пользователя

        Returns:
            Tuple(refresh_token, token_id, expires_at)
        """
        try:
            expire_time = datetime.utcnow() + self.refresh_token_expire
            token_id = str(uuid.uuid4())

            payload = {
                "sub": str(user_id),
                "type": "refresh",
                "exp": expire_time,
                "iat": datetime.utcnow(),
                "jti": token_id,
            }

            refresh_token = jwt.encode(
                payload,
                self.refresh_secret,
                algorithm=self.algorithm
            )

            logger.debug(f"Refresh token created for user {user_id}, expires: {expire_time}")
            return refresh_token, token_id, expire_time

        except Exception as e:
            logger.error(f"Error creating refresh token: {e}")
            raise

    def create_tokens(self, user_id: int, phone_number: str = None, full_name: str = None, role: str = None, email: str = None) -> Tuple[str, str, str, datetime]:
        """
        Создание пары токенов (access + refresh)

        Args:
            user_id: ID пользователя
            phone_number: Номер телефона (опционально)
            full_name: Полное имя пользователя (опционально)
            role: Роль пользователя (опционально)
            email: Email адрес (опционально)

        Returns:
            Tuple(access_token, refresh_token, token_id, expires_at)
        """
        try:
            access_token = self.create_access_token(user_id, phone_number, full_name, role, email)
            refresh_token, token_id, expires_at = self.create_refresh_token(user_id)

            logger.info(f"Token pair created for user {user_id}")
            return access_token, refresh_token, token_id, expires_at

        except Exception as e:
            logger.error(f"Error creating token pair: {e}")
            return None

    def verify_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Верификация access токена

        Args:
            token: Access токен

        Returns:
            dict с данными токена или None если невалидный
        """
        try:
            # Декодируем токен
            payload = jwt.decode(
                token,
                self.access_secret,
                algorithms=[self.algorithm],
                options={
                    "require": ["exp", "iat", "sub", "type", "jti"],
                    "verify_exp": True,
                    "verify_iat": True,
                }
            )

            # Проверяем тип токена
            if payload.get("type") != "access":
                logger.warning("Token is not an access token")
                return None

            # Извлекаем данные
            token_data = {
                "user_id": int(payload["sub"]),
                "phone": payload.get("phone"),
                "full_name": payload.get("name"),
                "role": payload.get("role"),
                "jti": payload.get("jti"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
            }

            logger.debug(f"Access token verified for user {token_data['user_id']}")
            return token_data

        except jwt.ExpiredSignatureError:
            logger.warning("Access token expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"JWT error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying access token: {e}")
            return None

    def verify_refresh_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Верификация refresh токена

        Args:
            token: Refresh токен

        Returns:
            dict с данными токена или None если невалидный
        """
        try:
            # Декодируем токен
            payload = jwt.decode(
                token,
                self.refresh_secret,
                algorithms=[self.algorithm],
                options={
                    "require": ["exp", "iat", "sub", "type", "jti"],
                    "verify_exp": True,
                    "verify_iat": True,
                }
            )

            # Проверяем тип токена
            if payload.get("type") != "refresh":
                logger.warning("Token is not a refresh token")
                return None

            # Извлекаем данные
            token_data = {
                "user_id": int(payload["sub"]),
                "jti": payload.get("jti"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
            }

            logger.debug(f"Refresh token verified for user {token_data['user_id']}")
            return token_data

        except jwt.ExpiredSignatureError:
            logger.warning("Refresh token expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"JWT error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying refresh token: {e}")
            return None

# Создаем глобальный инстанс сервиса
token_service = TokenService()