import logging
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.repositories.token_repository import TokenRepository
from app.services.token_service import token_service
from app.services.sms_service import sms_service
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class AuthService:
    """Сервис аутентификации с Firebase SMS"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = TokenRepository(db)

    async def request_sms_code(self, phone_number: str, full_name: str) -> bool:
        """
        Запрос отправки SMS кода через Firebase

        Args:
            phone_number: Номер телефона в формате +998XXXXXXXXX
            full_name: Полное имя пользователя

        Returns:
            bool: Успешно ли отправлен код
        """
        try:
            # Логируем запрос
            logger.info(f"Requesting SMS code for: {phone_number}, name: {full_name}")

            # Отправляем SMS через наш сервис (который использует Firebase)
            success, _ = await sms_service.send_sms(phone_number)

            if success:
                # Находим или создаем пользователя с именем (но не активируем пока)
                user = await self.user_repo.get_by_phone(phone_number)
                if not user:
                    # Создаем нового пользователя с именем
                    user = await self.user_repo.create_user(
                        phone_number=phone_number,
                        full_name=full_name,
                        is_verified=False,
                        is_active=False  # Активируем только после верификации кода
                    )
                    logger.info(f"New user created: {user.id} - {full_name}")
                else:
                    # Обновляем имя если оно изменилось
                    if user.full_name != full_name:
                        await self.user_repo.update_user(user.id, full_name=full_name)
                        logger.info(f"User name updated: {user.id} - {full_name}")
                    else:
                        logger.info(f"Existing user found: {user.id}")

            return success

        except Exception as e:
            logger.error(f"Error requesting SMS code: {e}", exc_info=True)
            return False

    async def verify_sms_code(
            self,
            phone_number: str,
            code: str
    ) -> Optional[Tuple[str, str, int]]:
        """
        Проверка SMS кода и выдача JWT токенов

        Args:
            phone_number: Номер телефона
            code: SMS код из сообщения

        Returns:
            Tuple[access_token, refresh_token, user_id] или None если ошибка
        """
        try:
            logger.info(f"Verifying code for: {phone_number}")

            # Проверяем код через SMS сервис (Firebase)
            verification_success, firebase_data = await sms_service.verify_code(phone_number, code)

            if not verification_success:
                logger.warning(f"Code verification failed for: {phone_number}")
                return None

            # Получаем или создаем пользователя
            user = await self.user_repo.get_by_phone(phone_number)

            if not user:
                # Если пользователь не найден, значит он не прошел request-code
                # Это не должно происходить, но на всякий случай
                logger.warning(f"User not found for phone: {phone_number}. User must request code first.")
                return None

            # Активируем и верифицируем пользователя после успешной проверки кода
            if not user.is_verified:
                await self.user_repo.update_user(
                    user.id,
                    is_verified=True,
                    is_active=True
                )
                logger.info(f"User activated and verified: {user.id}")
            else:
                # Активируем существующего пользователя
                if not user.is_verified:
                    await self.user_repo.update_user(
                        user.id,
                        is_verified=True,
                        is_active=True
                    )
                    logger.info(f"User activated: {user.id}")

                # Обновляем Firebase UID если нужно
                if firebase_data and "firebase_uid" in firebase_data and not user.firebase_uid:
                    await self.user_repo.update_user(
                        user.id,
                        firebase_uid=firebase_data["firebase_uid"]
                    )

            # Создаем JWT токены (включая роль)
            tokens = token_service.create_tokens(
                user_id=user.id,
                phone_number=user.phone_number,
                full_name=user.full_name,
                role=user.role
            )

            if not tokens:
                logger.error(f"Failed to create tokens for user: {user.id}")
                return None

            access_token, refresh_token, refresh_token_id, expires_at = tokens

            # Сохраняем refresh token в базу
            token_saved = await self.token_repo.create_refresh_token(
                user_id=user.id,
                token=refresh_token_id,
                expires_at=expires_at
            )

            if not token_saved:
                logger.error(f"Failed to save refresh token for user: {user.id}")
                return None

            logger.info(f"User authenticated successfully: {user.id}")

            return access_token, refresh_token, user.id

        except Exception as e:
            logger.error(f"Error verifying SMS code: {e}", exc_info=True)
            return None

    async def refresh_tokens(self, refresh_token: str) -> Optional[Tuple[str, str, int]]:
        """
        Обновление пары токенов с помощью refresh token

        Args:
            refresh_token: Refresh токен

        Returns:
            Tuple[new_access_token, new_refresh_token, user_id] или None
        """
        try:
            logger.info("Refreshing tokens")

            # Верифицируем refresh token
            payload = token_service.verify_refresh_token(refresh_token)
            if not payload:
                logger.warning("Invalid refresh token provided")
                return None

            user_id = payload.get("user_id")
            token_id = payload.get("jti")

            if not user_id or not token_id:
                logger.warning("Refresh token missing required claims")
                return None

            # Проверяем существование токена в базе
            db_token = await self.token_repo.get_refresh_token(token_id)
            if not db_token:
                logger.warning(f"Token not found in DB: {token_id}")
                return None

            # Проверяем активность и срок действия
            if not db_token.is_active:
                logger.warning(f"Token is inactive: {token_id}")
                return None

            if db_token.expires_at < datetime.utcnow():
                logger.warning(f"Token expired: {token_id}")
                # Деактивируем просроченный токен
                await self.token_repo.deactivate_token(token_id)
                return None

            # Проверяем пользователя
            user = await self.user_repo.get_by_id(user_id)
            if not user or not user.is_active:
                logger.warning(f"User not found or inactive: {user_id}")
                return None

            # Деактивируем старый refresh token
            await self.token_repo.deactivate_token(token_id)

            # Создаем новую пару токенов (включая роль)
            tokens = token_service.create_tokens(
                user_id=user.id,
                phone_number=user.phone_number,
                full_name=user.full_name,
                role=user.role
            )

            if not tokens:
                logger.error(f"Failed to create new tokens for user: {user.id}")
                return None

            new_access_token, new_refresh_token, new_token_id, expires_at = tokens

            # Сохраняем новый refresh token
            await self.token_repo.create_refresh_token(
                user_id=user.id,
                token=new_token_id,
                expires_at=expires_at
            )

            logger.info(f"Tokens refreshed for user: {user.id}")

            return new_access_token, new_refresh_token, user.id

        except Exception as e:
            logger.error(f"Error refreshing tokens: {e}", exc_info=True)
            return None

    async def logout(self, refresh_token: str) -> bool:
        """
        Выход из системы (инвалидация refresh token)

        Args:
            refresh_token: Refresh токен для инвалидации

        Returns:
            bool: Успешно ли выполнен выход
        """
        try:
            logger.info("Logout requested")

            # Верифицируем токен
            payload = token_service.verify_refresh_token(refresh_token)
            if not payload:
                logger.warning("Invalid token for logout")
                return False

            token_id = payload.get("jti")
            if not token_id:
                logger.warning("Token missing jti claim")
                return False

            # Деактивируем токен
            success = await self.token_repo.deactivate_token(token_id)

            if success:
                logger.info(f"Token deactivated: {token_id}")
            else:
                logger.warning(f"Failed to deactivate token: {token_id}")

            return success

        except Exception as e:
            logger.error(f"Error during logout: {e}")
            return False

    async def logout_all_sessions(self, user_id: int) -> bool:
        """
        Выход из всех устройств (инвалидация всех refresh токенов пользователя)

        Args:
            user_id: ID пользователя

        Returns:
            bool: Успешно ли выполнено
        """
        try:
            logger.info(f"Logout from all sessions for user: {user_id}")

            success = await self.token_repo.deactivate_all_user_tokens(user_id)

            if success:
                logger.info(f"All tokens deactivated for user: {user_id}")
            else:
                logger.warning(f"Failed to deactivate tokens for user: {user_id}")

            return success

        except Exception as e:
            logger.error(f"Error logging out from all sessions: {e}")
            return False

    async def validate_access_token(self, token: str) -> Optional[dict]:
        """
        Валидация access токена

        Args:
            token: Access токен

        Returns:
            dict: Данные пользователя или None
        """
        try:
            token_data = token_service.verify_access_token(token)
            if not token_data:
                return None

            # Проверяем что пользователь существует и активен
            user = await self.user_repo.get_by_id(token_data["user_id"])
            if not user or not user.is_active:
                return None

            return {
                "user_id": user.id,
                "phone_number": user.phone_number,
                "is_verified": user.is_verified
            }

        except Exception as e:
            logger.error(f"Error validating access token: {e}")
            return None

    async def request_email_code(self, email: str, full_name: str) -> bool:
        """
        Запрос отправки кода на email

        Args:
            email: Email адрес
            full_name: Полное имя пользователя

        Returns:
            bool: Успешно ли отправлен код
        """
        try:
            logger.info(f"Requesting email code for: {email}, name: {full_name}")

            # Отправляем код на email
            success, _ = await email_service.send_email(email)

            if success:
                # Находим или создаем пользователя с email (но не активируем пока)
                user = await self.user_repo.get_by_email(email)
                if not user:
                    # Создаем нового пользователя с email
                    user = await self.user_repo.create_user(
                        email=email,
                        full_name=full_name,
                        is_verified=False,
                        is_active=False  # Активируем только после верификации кода
                    )
                    logger.info(f"New user created: {user.id} - {full_name}")
                else:
                    # Обновляем имя если оно изменилось
                    if user.full_name != full_name:
                        await self.user_repo.update_user(user.id, full_name=full_name)
                        logger.info(f"User name updated: {user.id} - {full_name}")
                    else:
                        logger.info(f"Existing user found: {user.id}")

            return success

        except Exception as e:
            logger.error(f"Error requesting email code: {e}", exc_info=True)
            return False

    async def verify_email_code(
            self,
            email: str,
            code: str
    ) -> Optional[Tuple[str, str, int]]:
        """
        Проверка кода из email и выдача JWT токенов

        Args:
            email: Email адрес
            code: Код подтверждения из email

        Returns:
            Tuple[access_token, refresh_token, user_id] или None если ошибка
        """
        try:
            logger.info(f"Verifying email code for: {email}")

            # Проверяем код через email сервис
            verification_success, email_data = await email_service.verify_code(email, code)

            if not verification_success:
                logger.warning(f"Email code verification failed for: {email}")
                return None

            # Получаем пользователя по email
            user = await self.user_repo.get_by_email(email)

            if not user:
                # Если пользователь не найден, значит он не прошел request-code
                logger.warning(f"User not found for email: {email}. User must request code first.")
                return None

            # Активируем и верифицируем пользователя после успешной проверки кода
            if not user.is_verified:
                await self.user_repo.update_user(
                    user.id,
                    is_verified=True,
                    is_active=True
                )
                logger.info(f"User activated and verified: {user.id}")

            # Создаем JWT токены (включая роль)
            tokens = token_service.create_tokens(
                user_id=user.id,
                phone_number=user.phone_number,
                full_name=user.full_name,
                role=user.role,
                email=user.email
            )

            if not tokens:
                logger.error(f"Failed to create tokens for user: {user.id}")
                return None

            access_token, refresh_token, refresh_token_id, expires_at = tokens

            # Сохраняем refresh token в базу
            token_saved = await self.token_repo.create_refresh_token(
                user_id=user.id,
                token=refresh_token_id,
                expires_at=expires_at
            )

            if not token_saved:
                logger.error(f"Failed to save refresh token for user: {user.id}")
                return None

            logger.info(f"User authenticated successfully via email: {user.id}")

            return access_token, refresh_token, user.id

        except Exception as e:
            logger.error(f"Error verifying email code: {e}", exc_info=True)
            return None