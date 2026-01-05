import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from jose import JWTError, jwt
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenService:
    """Сервис для работы с JWT токенами"""

    def __init__(self):
        self.access_secret = settings.JWT_SECRET_KEY
        self.refresh_secret = settings.JWT_REFRESH_SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    def create_access_token(self, user_id: int, phone_number: str, full_name: str = None, role: str = None) -> str:
        """
        Создание access токена

        Args:
            user_id: ID пользователя
            phone_number: Номер телефона
            full_name: Полное имя пользователя (опционально)
            role: Роль пользователя (опционально)

        Returns:
            Access токен в виде строки
        """
        try:
            expire_time = datetime.utcnow() + self.access_token_expire
            token_id = str(uuid.uuid4())

            # Базовые данные
            payload = {
                "sub": str(user_id),
                "phone": phone_number,
                "type": "access",
                "exp": expire_time,
                "iat": datetime.utcnow(),
                "jti": token_id,
            }

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

    def create_tokens(self, user_id: int, phone_number: str, full_name: str = None, role: str = None) -> Tuple[str, str, str, datetime]:
        """
        Создание пары токенов (access + refresh)

        Args:
            user_id: ID пользователя
            phone_number: Номер телефона
            full_name: Полное имя пользователя (опционально)
            role: Роль пользователя (опционально)

        Returns:
            Tuple(access_token, refresh_token, token_id, expires_at)
        """
        try:
            access_token = self.create_access_token(user_id, phone_number, full_name, role)
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

    def decode_token_without_verification(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Декодирование токена без проверки подписи (для отладки)

        Args:
            token: Токен для декодирования

        Returns:
            dict с данными токена или None если ошибка
        """
        try:
            payload = jwt.get_unverified_claims(token)
            return {
                "user_id": int(payload.get("sub", 0)) if payload.get("sub") else None,
                "phone": payload.get("phone"),
                "full_name": payload.get("name"),
                "type": payload.get("type"),
                "jti": payload.get("jti"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
            }
        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            return None

    def extract_token_from_header(self, authorization_header: str) -> Optional[str]:
        """
        Извлечение токена из заголовка Authorization

        Args:
            authorization_header: Заголовок Authorization

        Returns:
            Токен или None если формат неверный
        """
        if not authorization_header:
            return None

        try:
            # Формат: Bearer <token>
            parts = authorization_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                logger.warning(f"Invalid Authorization header format: {authorization_header}")
                return None

            token = parts[1]
            return token

        except Exception as e:
            logger.error(f"Error extracting token from header: {e}")
            return None

    def get_token_expiry_time(self, token: str, token_type: str = "access") -> Optional[datetime]:
        """
        Получение времени истечения токена

        Args:
            token: Токен
            token_type: Тип токена ('access' или 'refresh')

        Returns:
            datetime или None если ошибка
        """
        try:
            if token_type == "access":
                payload = jwt.decode(
                    token,
                    self.access_secret,
                    algorithms=[self.algorithm],
                    options={"verify_exp": False}
                )
            else:
                payload = jwt.decode(
                    token,
                    self.refresh_secret,
                    algorithms=[self.algorithm],
                    options={"verify_exp": False}
                )

            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                return datetime.utcfromtimestamp(exp_timestamp)
            return None

        except Exception as e:
            logger.error(f"Error getting token expiry: {e}")
            return None

    def is_token_expired(self, token: str, token_type: str = "access") -> bool:
        """
        Проверка истек ли срок действия токена

        Args:
            token: Токен
            token_type: Тип токена

        Returns:
            True если токен истек, False если нет или ошибка
        """
        expiry_time = self.get_token_expiry_time(token, token_type)
        if not expiry_time:
            return True

        return datetime.utcnow() > expiry_time

    def get_remaining_token_lifetime(self, token: str, token_type: str = "access") -> Optional[int]:
        """
        Получение оставшегося времени жизни токена в секундах

        Args:
            token: Токен
            token_type: Тип токена

        Returns:
            Количество секунд до истечения или None если ошибка
        """
        expiry_time = self.get_token_expiry_time(token, token_type)
        if not expiry_time:
            return None

        remaining = expiry_time - datetime.utcnow()
        return int(remaining.total_seconds()) if remaining.total_seconds() > 0 else 0

    def create_admin_token(self, user_id: int, roles: list = None, permissions: list = None) -> str:
        """
        Создание административного токена с дополнительными claims

        Args:
            user_id: ID пользователя
            roles: Список ролей
            permissions: Список разрешений

        Returns:
            Admin токен
        """
        try:
            expire_time = datetime.utcnow() + timedelta(hours=1)  # Admin токены живут 1 час
            token_id = str(uuid.uuid4())

            payload = {
                "sub": str(user_id),
                "type": "admin",
                "exp": expire_time,
                "iat": datetime.utcnow(),
                "jti": token_id,
            }

            # Добавляем роли и разрешения если есть
            if roles:
                payload["roles"] = roles
            if permissions:
                payload["permissions"] = permissions

            admin_token = jwt.encode(
                payload,
                self.access_secret,  # Используем тот же секрет
                algorithm=self.algorithm
            )

            logger.info(f"Admin token created for user {user_id}")
            return admin_token

        except Exception as e:
            logger.error(f"Error creating admin token: {e}")
            raise

    def verify_admin_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Верификация административного токена

        Args:
            token: Admin токен

        Returns:
            dict с данными токена или None
        """
        try:
            payload = jwt.decode(
                token,
                self.access_secret,
                algorithms=[self.algorithm],
                options={
                    "require": ["exp", "iat", "sub", "type"],
                    "verify_exp": True,
                    "verify_iat": True,
                }
            )

            if payload.get("type") != "admin":
                logger.warning("Token is not an admin token")
                return None

            return {
                "user_id": int(payload["sub"]),
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", []),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
            }

        except jwt.ExpiredSignatureError:
            logger.warning("Admin token expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"JWT error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying admin token: {e}")
            return None

    def rotate_secrets(self, new_access_secret: str, new_refresh_secret: str):
        """
        Ротация секретных ключей (для production)

        Args:
            new_access_secret: Новый секрет для access токенов
            new_refresh_secret: Новый секрет для refresh токенов
        """
        old_access_secret = self.access_secret
        old_refresh_secret = self.refresh_secret

        self.access_secret = new_access_secret
        self.refresh_secret = new_refresh_secret

        logger.info("Token secrets rotated successfully")

        # Можно сохранить старые секреты на некоторое время
        # для постепенной миграции существующих токенов
        return {
            "old_access_secret": old_access_secret[:10] + "...",  # Логируем только часть
            "old_refresh_secret": old_refresh_secret[:10] + "...",
        }


# Создаем глобальный инстанс сервиса
token_service = TokenService()