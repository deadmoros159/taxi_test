from pydantic import BaseModel, Field, EmailStr, validator
import phonenumbers
from typing import Optional
import re


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
    """Ответ с JWT токенами"""
    access_token: str = Field(..., description="JWT access token (живет 1 час)")
    refresh_token: str = Field(..., description="JWT refresh token (живет 30 дней)")
    token_type: str = Field(default="bearer", description="Тип токена")
    expires_in: int = Field(..., description="Время жизни access токена в секундах (3600)")
    user_id: int = Field(..., description="ID пользователя")

    # Опциональные поля пользователя
    full_name: Optional[str] = Field(None, description="Полное имя пользователя")
    email: Optional[EmailStr] = Field(None, description="Email пользователя")
    phone_number: Optional[str] = Field(None, description="Номер телефона пользователя")


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
    """Авторизация через Telegram (без SMS кода)"""
    phone_number: str = Field(..., description="Номер телефона из Telegram")
    full_name: str = Field(..., description="Полное имя пользователя из Telegram")
    telegram_user_id: int = Field(..., description="ID пользователя в Telegram")
    telegram_username: Optional[str] = Field(None, description="Username в Telegram")

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