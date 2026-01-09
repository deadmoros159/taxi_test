import httpx
import json
import logging
import time
from typing import Optional, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)


class FirebaseSMSService:
    """
    Сервис для отправки SMS кодов через Firebase Phone Auth
    ТОЛЬКО отправка SMS, верификацию делаем сами
    """

    def __init__(self):
        self.api_key = settings.FIREBASE_API_KEY.get_secret_value() if settings.FIREBASE_API_KEY else None
        self.project_id = settings.FIREBASE_PROJECT_ID
        self.client = httpx.AsyncClient(timeout=30.0)

        # reCAPTCHA токен (в production получается на фронтенде)
        self.recaptcha_token = "NOT_NEEDED_FOR_BACKEND"
        # На самом деле reCAPTCHA нужна только на клиенте

    async def send_verification_code(self, phone_number: str) -> Tuple[bool, Optional[str]]:
        """
        Отправка SMS кода через Firebase

        Возвращает: (success, session_info)
        session_info нужно сохранить для верификации кода
        """
        if not self.api_key:
            logger.error("Firebase API key is not configured")
            return False, None

        # Проверяем, является ли номер тестовым
        formatted_phone = self._format_phone_number(phone_number)
        test_code = self._check_test_phone(formatted_phone)

        if test_code:
            # Это тестовый номер - возвращаем моковую сессию
            logger.info(f"✅ Using test phone number: {formatted_phone} (code: {test_code})")
            # Создаем моковую session_info для тестового номера
            mock_session = f"test_session_{formatted_phone}_{int(time.time())}"
            return True, mock_session

        try:
            logger.info(f"Attempting to send SMS to: {formatted_phone}")

            # Шаг 1: Запрос на отправку SMS
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode?key={self.api_key}"

            # Для backend запросов можно попробовать без reCAPTCHA или с пустым токеном
            # В некоторых случаях Firebase может работать без него для тестирования
            payload = {
                "phoneNumber": formatted_phone
            }

            # Добавляем reCAPTCHA только если он есть (для production)
            if self.recaptcha_token and self.recaptcha_token != "NOT_NEEDED_FOR_BACKEND":
                payload["recaptchaToken"] = self.recaptcha_token

            logger.debug(f"Firebase request URL: {url.split('?')[0]}...")
            logger.debug(f"Firebase payload: {payload}")

            response = await self.client.post(url, json=payload)

            logger.info(f"Firebase response status: {response.status_code}")
            logger.debug(f"Firebase response headers: {dict(response.headers)}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Firebase response data: {data}")
                session_info = data.get("sessionInfo")

                if session_info:
                    logger.info(f"✅ Firebase SMS sent to {phone_number}, session: {session_info[:20]}...")
                    return True, session_info
                else:
                    logger.error(f"❌ Firebase returned 200 but no sessionInfo in response: {data}")
                    return False, None
            else:
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                error_code = error_data.get("error", {}).get("code", "UNKNOWN")

                logger.error(f"Firebase SMS error: {error_code} : {error_message}")
                # Логируем полную ошибку для отладки
                logger.error(f"Full Firebase error response: {error_data}")

                # Если ошибка связана с биллингом
                if "BILLING_NOT_ENABLED" in str(error_data) or "BILLING_NOT_ENABLED" in error_message:
                    logger.error("=" * 60)
                    logger.error("⚠️  КРИТИЧНО: В Firebase проекте не включен биллинг!")
                    logger.error("=" * 60)
                    logger.error("РЕШЕНИЕ:")
                    logger.error("1. Откройте Firebase Console: https://console.firebase.google.com")
                    logger.error("2. Выберите ваш проект: taxi-a0931")
                    logger.error("3. Перейдите: Project Settings (⚙️) -> Billing")
                    logger.error("4. Подключите платежный метод (Blaze plan - pay-as-you-go)")
                    logger.error("5. БЕЗ БИЛЛИНГА SMS НЕ БУДУТ ОТПРАВЛЯТЬСЯ!")
                    logger.error("")
                    logger.error("АЛЬТЕРНАТИВА для разработки:")
                    logger.error("1. Firebase Console -> Authentication -> Sign-in method -> Phone")
                    logger.error("2. Найдите 'Test phone numbers'")
                    logger.error("3. Добавьте тестовый номер (например, +998901234567 с кодом 123456)")
                    logger.error("4. Тестовые номера работают БЕЗ биллинга")
                    logger.error("=" * 60)
                # Если ошибка связана с регионом
                elif "OPERATION_NOT_ALLOWED" in str(error_data) or "region" in error_message.lower():
                    logger.error(
                        "⚠️  ВАЖНО: Проверьте в Firebase Console:\n"
                        "1. Authentication -> Sign-in method -> Phone -> Enable\n"
                        "2. Убедитесь, что регионы (Россия +7, Узбекистан +998) включены\n"
                        "3. Для разработки добавьте тестовые номера в Authentication -> Phone -> Test phone numbers\n"
                        "4. Изменения могут применяться до 10 минут"
                    )

                return False, None

        except Exception as e:
            logger.error(f"Firebase SMS exception: {e}", exc_info=True)
            return False, None

    async def verify_code(self, session_info: str, code: str, phone_number: Optional[str] = None) -> Tuple[
        bool, Optional[dict]]:
        """
        Проверка кода через Firebase

        Возвращает: (success, user_data)
        user_data содержит phone_number и другие данные
        """
        # Проверяем, является ли это тестовым номером
        if phone_number:
            formatted_phone = self._format_phone_number(phone_number)
            test_code = self._check_test_phone(formatted_phone)

            if test_code and code == test_code:
                # Это тестовый номер с правильным кодом
                logger.info(f"✅ Test phone verification successful: {formatted_phone}")
                return True, {
                    "phone_number": formatted_phone,
                    "firebase_uid": f"test_uid_{formatted_phone}",
                    "is_new_user": True
                }

        try:
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPhoneNumber?key={self.api_key}"

            payload = {
                "sessionInfo": session_info,
                "code": code,
                "operation": "SIGN_IN_OR_UP"
            }

            response = await self.client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()

                # Извлекаем данные пользователя
                user_data = {
                    "phone_number": data.get("phoneNumber"),
                    "firebase_uid": data.get("localId"),
                    "id_token": data.get("idToken"),  # Firebase ID токен
                    "refresh_token": data.get("refreshToken"),
                    "is_new_user": data.get("isNewUser", False)
                }

                logger.info(f"Firebase code verified for {user_data['phone_number']}")
                return True, user_data
            else:
                error_data = response.json()
                logger.error(f"Firebase verification error: {error_data}")
                return False, None

        except Exception as e:
            logger.error(f"Firebase verification exception: {e}")
            return False, None

    def _format_phone_number(self, phone: str) -> str:
        """Форматирование номера для Firebase"""
        # Убираем все нецифровые символы кроме +
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')

        # Если нет + в начале, добавляем
        if not cleaned.startswith('+'):
            # Предполагаем, что номер из Узбекистана
            if cleaned.startswith('998'):
                cleaned = '+' + cleaned
            elif len(cleaned) == 10:  # Без кода страны
                cleaned = '+998' + cleaned
            else:
                cleaned = '+' + cleaned

        return cleaned

    def _check_test_phone(self, phone_number: str) -> Optional[str]:
        """
        Проверяет, является ли номер тестовым номером Firebase

        Возвращает код для тестового номера или None
        """
        test_phones = settings.FIREBASE_TEST_PHONES
        if not test_phones:
            return None

        for test_phone_config in test_phones:
            if ':' in test_phone_config:
                test_phone, test_code = test_phone_config.split(':', 1)
                # Форматируем тестовый номер для сравнения
                formatted_test = self._format_phone_number(test_phone)
                if formatted_test == phone_number:
                    return test_code.strip()

        return None

    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()


# Глобальный инстанс
firebase_sms_service = FirebaseSMSService()