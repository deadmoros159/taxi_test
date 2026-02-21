from pydantic import BaseModel, Field, EmailStr, validator
import phonenumbers
from typing import Optional
import re

MAX_BCRYPT_PASSWORD_BYTES = 72


def _validate_password_bcrypt_limit(v: str) -> str:
    # bcrypt max 72 bytes; enforce to avoid 500s
    if v is None:
        return v
    if len(v.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError(f"Password too long (max {MAX_BCRYPT_PASSWORD_BYTES} bytes)")
    return v


class PhoneAuthRequest(BaseModel):
    """Запрос SMS кода на телефон"""
    phone_number: str = Field(..., description="Номер телефона в формате +998XXXXXXXXX")
    full_name: Optional[str] = Field(None, description="Полное имя пользователя (для регистрации)")

    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v:
            try:
                phone = phonenumbers.parse(v, None)
                if not phonenumbers.is_valid_number(phone):
                    raise ValueError("Invalid phone number")
                return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)
            except:
                raise ValueError("Invalid phone number format")
        return v


class EmailAuthRequest(BaseModel):
    """Запрос кода на email"""
    email: EmailStr = Field(..., description="Адрес электронной почты")
    full_name: Optional[str] = Field(None, description="Полное имя пользователя (для регистрации)")


class VerifyPhoneCodeRequest(BaseModel):
    """Проверка SMS кода"""
    phone_number: str = Field(..., description="Номер телефона")
    code: str = Field(..., min_length=4, max_length=6, description="Код подтверждения")


class VerifyEmailCodeRequest(BaseModel):
    """Проверка email кода"""
    email: EmailStr = Field(..., description="Адрес электронной почты")
    code: str = Field(..., min_length=4, max_length=6, description="Код подтверждения")


class TokensResponse(BaseModel):
    """Ответ с JWT токенами (только токены, без данных пользователя)"""
    access_token: str = Field(..., description="JWT access token (живет 1 час)")
    refresh_token: str = Field(..., description="JWT refresh token (живет 30 дней)")
    token_type: str = Field(default="bearer", description="Тип токена")
    expires_in: int = Field(..., description="Время жизни access токена в секундах (3600)")
    user_id: Optional[str] = Field(None, description="ID пользователя (для Telegram бота и др.)")


# Для обратной совместимости (можно удалить позже)
class AuthRequest(BaseModel):
    """Старая схема (deprecated)"""
    phone_number: Optional[str] = Field(None, description="Номер телефона в формате +998XXXXXXXXX")
    email: Optional[str] = Field(None, description="Адрес электронной почты")
    full_name: Optional[str] = Field(None, description="Полное имя пользователя")


class VerifyCodeRequest(BaseModel):
    """Старая схема (deprecated)"""
    phone_number: Optional[str] = None
    email: Optional[str] = None
    code: str = Field(..., min_length=4, max_length=6)


class TelegramAuthRequest(BaseModel):
    """
    Авторизация через Telegram (для Flutter/мобильных приложений).
    
    Принимает данные от Telegram SDK/API и создает/находит пользователя.
    Все данные (имя, телефон, фото) автоматически сохраняются в БД.
    """
    phone_number: str = Field(..., description="Номер телефона из Telegram")
    full_name: str = Field(..., description="Полное имя пользователя из Telegram")
    telegram_user_id: int = Field(..., description="ID пользователя в Telegram")
    telegram_username: Optional[str] = Field(None, description="Username в Telegram")
    photo_id: Optional[int] = Field(None, description="ID фото профиля в media-service (опционально)")
    email: Optional[str] = Field(None, description="Email пользователя (если доступен, опционально)")
    photo_url: Optional[str] = Field(None, description="URL фото профиля из Telegram (опционально, deprecated - используйте photo_id)")
    auth_date: Optional[int] = Field(None, description="Дата авторизации в Telegram (Unix timestamp, опционально)")
    hash: Optional[str] = Field(None, description="Хеш для проверки подписи данных (опционально, для безопасности)")

    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v:
            try:
                phone = phonenumbers.parse(v, None)
                if not phonenumbers.is_valid_number(phone):
                    raise ValueError("Invalid phone number")
                return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)
            except:
                raise ValueError("Invalid phone number format")
        return v


class TelegramUserCheckResponse(BaseModel):
    """Проверка: существует ли пользователь Telegram в БД"""
    exists: bool = Field(..., description="Есть ли пользователь в БД")
    user_id: Optional[int] = Field(None, description="ID пользователя в системе (если exists=true)")
    full_name: Optional[str] = Field(None, description="Имя пользователя (если exists=true)")
    phone_number: Optional[str] = Field(None, description="Телефон (если есть)")


class TelegramIdAuthRequest(BaseModel):
    """Авторизация через Telegram по telegram_user_id (без отправки контакта)"""
    telegram_user_id: int = Field(..., description="ID пользователя в Telegram")


class PhoneAuthForAppRequest(BaseModel):
    """Авторизация по номеру телефона (для Flutter/мобильных приложений)"""
    phone_number: str = Field(..., description="Номер телефона (должен быть зарегистрирован через Telegram бот)")
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v:
            try:
                phone = phonenumbers.parse(v, None)
                if not phonenumbers.is_valid_number(phone):
                    raise ValueError("Invalid phone number")
                return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)
            except:
                raise ValueError("Invalid phone number format")
        return v


class AdminRegisterRequest(BaseModel):
    """Регистрация администратора по email/password (публичная)"""
    email: EmailStr = Field(..., description="Email администратора")
    password: str = Field(..., min_length=6, description="Пароль (bcrypt max 72 bytes)")
    _pw = validator("password", allow_reuse=True)(_validate_password_bcrypt_limit)


class AdminLoginRequest(BaseModel):
    """Вход администратора по email/password (публичная)"""
    email: EmailStr = Field(..., description="Email администратора")
    password: str = Field(..., description="Пароль")
    _pw = validator("password", allow_reuse=True)(_validate_password_bcrypt_limit)


class DispatcherRegisterRequest(BaseModel):
    """Регистрация диспетчера (создание аккаунта)"""
    email: EmailStr = Field(..., description="Email диспетчера")
    password: str = Field(..., min_length=6, description="Пароль диспетчера (bcrypt max 72 bytes)")
    full_name: str = Field(..., description="Полное имя диспетчера")
    _pw = validator("password", allow_reuse=True)(_validate_password_bcrypt_limit)


class StaffLoginRequest(BaseModel):
    """Вход сотрудника (dispatcher/driver) по email/password"""
    email: EmailStr = Field(..., description="Email сотрудника")
    password: str = Field(..., description="Пароль")
    _pw = validator("password", allow_reuse=True)(_validate_password_bcrypt_limit)