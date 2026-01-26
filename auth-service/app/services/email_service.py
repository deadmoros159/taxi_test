import logging
import time
import random
import string
import ssl
from typing import Optional, Tuple
from app.core.config import settings
import redis.asyncio as redis
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import structlog

logger = structlog.get_logger(__name__)


class EmailService:
    """
    Сервис для отправки кодов подтверждения на email
    Использует SMTP для отправки, Redis для хранения кодов
    """

    def __init__(self):
        self.redis = None
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else ""
        self.sender_email = settings.SENDER_EMAIL

    async def initialize(self):
        """Инициализация Redis"""
        if not self.redis:
            try:
                redis_url = str(settings.REDIS_URL)
                safe_url = redis_url.split('@')[-1] if '@' in redis_url else redis_url
                logger.info(event="redis_connect_attempt", redis_url=safe_url, message="Connecting to Redis for Email Service")
                
                self.redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                await self.redis.ping()
                logger.info(event="redis_connected", message="Email Service Redis connection established")
            except Exception as e:
                logger.error(event="redis_connect_failed", error=str(e), exc_info=True, message="Failed to connect to Redis in Email service")
                if settings.DEBUG:
                    logger.warning(event="redis_continue_without", message="Continuing without Redis in DEBUG mode")
                    self.redis = None
                else:
                    raise

    def _generate_code(self) -> str:
        """Генерация кода подтверждения"""
        length = settings.EMAIL_CODE_LENGTH
        return ''.join(random.choices(string.digits, k=length))

    async def send_email(self, email: str) -> Tuple[bool, Optional[str]]:
        """
        Отправка кода подтверждения на email

        Args:
            email: Email адрес получателя

        Returns:
            Tuple[success, code] - успех отправки и код (для mock режима)
        """
        await self.initialize()

        # Определяем ключи для Redis
        rate_key = f"email_rate:{email}"
        attempts_key = f"email_attempts:{email}"
        code_key = f"email_code:{email}"

        # Проверяем rate limit
        if self.redis:
            try:
                # Проверяем количество попыток
                attempts = await self.redis.get(attempts_key)
                if attempts and int(attempts) >= settings.EMAIL_MAX_ATTEMPTS:
                    logger.warning(event="email_rate_limit_exceeded", email=email, attempts=attempts, max_attempts=settings.EMAIL_MAX_ATTEMPTS, message="Email rate limit exceeded")
                    return False, None

                # Проверяем cooldown
                last_sent = await self.redis.get(rate_key)
                if last_sent:
                    time_passed = time.time() - float(last_sent)
                    if time_passed < settings.EMAIL_COOLDOWN_SECONDS:
                        remaining = settings.EMAIL_COOLDOWN_SECONDS - time_passed
                        logger.warning(event="email_cooldown_active", email=email, remaining_seconds=round(remaining, 1), message="Email cooldown active")
                        return False, None
            except Exception as e:
                logger.error(event="rate_limit_check_failed", error=str(e), message="Failed to check rate limit")

        # Всегда используем реальный SMTP (mock режим отключен)
        # Генерируем код
        code = self._generate_code()
        
        # Реальная отправка через SMTP
        logger.info(event="smtp_send_attempt", email=email, server=self.smtp_server, port=self.smtp_port, username=self.smtp_username, message="Attempting to send email via SMTP")
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = "Код подтверждения"
            message["From"] = self.sender_email
            message["To"] = email

            # Текст письма
            text = f"""
            Ваш код подтверждения: {code}
            
            Код действителен в течение {settings.EMAIL_CODE_EXPIRE_SECONDS // 60} минут.
            
            Если вы не запрашивали этот код, проигнорируйте это письмо.
            """
            
            html = f"""
            <html>
              <body>
                <h2>Код подтверждения</h2>
                <p>Ваш код подтверждения: <strong>{code}</strong></p>
                <p>Код действителен в течение {settings.EMAIL_CODE_EXPIRE_SECONDS // 60} минут.</p>
                <p>Если вы не запрашивали этот код, проигнорируйте это письмо.</p>
              </body>
            </html>
            """

            part1 = MIMEText(text, "plain", "utf-8")
            part2 = MIMEText(html, "html", "utf-8")

            message.attach(part1)
            message.attach(part2)

            logger.info(event="smtp_connect", server=self.smtp_server, port=self.smtp_port, message="Connecting to SMTP server")
            
            # Отправка через SMTP
            # Для порта 465 используем SSL, для 587 - STARTTLS
            use_tls = self.smtp_port == 587  # STARTTLS для порта 587
            use_ssl = self.smtp_port == 465  # SSL для порта 465
            
            # Создаем SSL контекст
            # Если указан путь к сертификату - используем его, иначе отключаем проверку (для самоподписанных)
            if settings.SMTP_SSL_CERT_PATH:
                # Используем существующий сертификат с сервера
                ssl_context = ssl.create_default_context(cafile=settings.SMTP_SSL_CERT_PATH)
                logger.info(event="smtp_using_cert", cert_path=settings.SMTP_SSL_CERT_PATH, message="Using existing SSL certificate")
            else:
                # Для самоподписанных сертификатов отключаем проверку
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                logger.info(event="smtp_no_cert_verify", message="SSL certificate verification disabled for self-signed certificate")
            
            try:
                if use_ssl:
                    # Для порта 465 используем SSL (TLS с самого начала)
                    await aiosmtplib.send(
                        message,
                        hostname=self.smtp_server,
                        port=self.smtp_port,
                        username=self.smtp_username,
                        password=self.smtp_password,
                        use_tls=True,  # SSL/TLS с самого начала
                        start_tls=False,
                        tls_context=ssl_context,  # Используем наш SSL контекст
                    )
                else:
                    # Для порта 587 используем STARTTLS (обычное соединение, затем TLS)
                    # Важно: для STARTTLS тоже нужно передать tls_context
                    await aiosmtplib.send(
                        message,
                        hostname=self.smtp_server,
                        port=self.smtp_port,
                        username=self.smtp_username,
                        password=self.smtp_password,
                        start_tls=use_tls,  # True для порта 587
                        tls_context=ssl_context,  # SSL контекст для STARTTLS
                        use_tls=False,  # Не используем TLS с самого начала
                    )
                
                logger.info(event="email_sent_success", email=email, code=code, message="Email sent successfully")
            except Exception as smtp_error:
                logger.error(event="smtp_error", error_type=type(smtp_error).__name__, error_message=str(smtp_error), exc_info=True, message="SMTP error")
                raise

            # Сохраняем код в Redis
            if not self.redis:
                await self.initialize()
            
            if self.redis:
                code_key = f"email_code:{email}"
                try:
                    await self.redis.setex(
                        code_key,
                        settings.EMAIL_CODE_EXPIRE_SECONDS,
                        code
                    )
                    await self.redis.setex(
                        rate_key,
                        settings.EMAIL_COOLDOWN_SECONDS,
                        str(time.time())
                    )
                    await self.redis.incr(attempts_key)
                    await self.redis.expire(attempts_key, 86400)
                except Exception as e:
                    logger.error(event="redis_save_failed", error=str(e), message="Failed to save code to Redis")

            return True, None  # Не возвращаем код в production

        except Exception as e:
            logger.error(event="email_send_failed", error=str(e), exc_info=True, message="Failed to send email")
            return False, None

    async def verify_code(self, email: str, code: str) -> Tuple[bool, Optional[dict]]:
        """
        Проверка кода подтверждения из email

        Args:
            email: Email адрес
            code: Код подтверждения

        Returns:
            Tuple[success, user_data]
        """
        await self.initialize()

        if not self.redis:
            logger.error(event="redis_not_available", message="Redis not available for email verification")
            return False, None

        code_key = f"email_code:{email}"
        
        try:
            stored_code = await self.redis.get(code_key)
            
            if not stored_code:
                logger.warning(event="email_code_not_found", email=email, message="No code found for email")
                return False, None

            if stored_code != code:
                logger.warning(event="email_code_invalid", email=email, message="Invalid code for email")
                return False, None

            # Код верный - удаляем его
            await self.redis.delete(code_key)
            
            # Сбрасываем счетчик попыток
            attempts_key = f"email_attempts:{email}"
            await self.redis.delete(attempts_key)

            logger.info(event="email_code_verified", email=email, message="Email code verified successfully")
            
            return True, {"email": email}

        except Exception as e:
            logger.error(event="email_verify_failed", error=str(e), exc_info=True, message="Failed to verify email code")
            return False, None


# Создаем глобальный экземпляр
email_service = EmailService()
