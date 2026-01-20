from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.auth import (
    PhoneAuthRequest, 
    EmailAuthRequest,
    VerifyCodeRequest, 
    VerifyPhoneCodeRequest,
    VerifyEmailCodeRequest,
    TelegramAuthRequest,
    AdminRegisterRequest,
    AdminLoginRequest,
    TokensResponse
)
from app.schemas.token import RefreshTokenRequest
from app.services.auth_service import AuthService
from app.utils.rate_limiter import rate_limiter
from app.api.v1.dependencies import get_current_user
from app.models.role import UserRole
from app.utils.password import hash_password, verify_password

router = APIRouter()

# Подроутеры для phone, email и telegram
phone_router = APIRouter()
email_router = APIRouter()
telegram_router = APIRouter()
admin_router = APIRouter()


@phone_router.post("/request", response_model=dict)
async def request_phone_code(
        request: Request,
        phone_request: PhoneAuthRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Запрос SMS кода для входа.

    Пользователь вводит имя и номер телефона, на номер отправляется SMS код.

    Rate limited: 10 запросов в минуту с одного IP
    """
    # Проверка rate limit
    await rate_limiter.check_request_limit(request, phone_request.phone_number)

    auth_service = AuthService(db)
    success = await auth_service.request_sms_code(
        phone_number=phone_request.phone_number,
        full_name=phone_request.full_name
    )

    if not success:
        # Проверяем, используется ли mock режим
        from app.core.config import settings
        if settings.SMS_PROVIDER == "mock":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send SMS code in mock mode. Please check server logs."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send SMS code. Please check Firebase configuration or try again later."
            )

    return {
        "message": "SMS code sent successfully",
        "expires_in": 300  # 5 минут
    }


@phone_router.post("/verify", response_model=TokensResponse)
async def verify_phone_code(
        request: Request,
        verify_request: VerifyPhoneCodeRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Проверка SMS кода и получение токенов.
    """
    # Проверка rate limit для верификации
    await rate_limiter.check_request_limit(
        request,
        f"verify:{verify_request.phone_number}"
    )

    auth_service = AuthService(db)
    result = await auth_service.verify_sms_code(
        verify_request.phone_number,
        verify_request.code
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid code or phone number",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token, user_id = result
    
    # Получаем информацию о пользователе для ответа
    from app.repositories.user_repository import UserRepository
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    return TokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=900,  # 15 минут
        user_id=user_id,
        full_name=user.full_name if user else None,
        phone_number=user.phone_number if user else None
    )


@email_router.post("/request", response_model=dict)
async def request_email_code(
        request: Request,
        email_request: EmailAuthRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Запрос кода на email для входа.

    Пользователь вводит email и имя, на email отправляется код подтверждения.

    Rate limited: 10 запросов в минуту с одного IP
    """
    # Проверка rate limit
    await rate_limiter.check_request_limit(request, email_request.email)

    auth_service = AuthService(db)
    success = await auth_service.request_email_code(
        email=email_request.email,
        full_name=email_request.full_name or "User"
    )

    if not success:
        from app.core.config import settings
        if settings.ENVIRONMENT == "development":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email code. Please check SMTP configuration or try again later."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email code. Please try again later."
            )

    return {
        "message": "Email code sent successfully",
        "expires_in": 300  # 5 минут
    }


@email_router.post("/verify", response_model=TokensResponse)
async def verify_email_code(
        request: Request,
        verify_request: VerifyEmailCodeRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Проверка кода из email и получение токенов.
    """
    # Проверка rate limit для верификации
    await rate_limiter.check_request_limit(
        request,
        f"verify_email:{verify_request.email}"
    )

    auth_service = AuthService(db)
    result = await auth_service.verify_email_code(
        verify_request.email,
        verify_request.code
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid code or email",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token, user_id = result
    
    # Получаем информацию о пользователе для ответа
    from app.repositories.user_repository import UserRepository
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    return TokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=900,  # 15 минут
        user_id=user_id,
        full_name=user.full_name if user else None,
        email=user.email if user else None
    )


@telegram_router.post("/authorize", response_model=TokensResponse)
async def authorize_via_telegram(
        request: Request,
        telegram_request: TelegramAuthRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Авторизация через Telegram (без SMS кода).

    Telegram уже подтвердил номер телефона, поэтому мы сразу создаем/находим
    пользователя и выдаем JWT токены.
    """
    # Проверка rate limit
    await rate_limiter.check_request_limit(
        request,
        f"telegram:{telegram_request.phone_number}"
    )

    auth_service = AuthService(db)
    result = await auth_service.authorize_via_telegram(
        phone_number=telegram_request.phone_number,
        full_name=telegram_request.full_name,
        telegram_user_id=telegram_request.telegram_user_id,
        telegram_username=telegram_request.telegram_username
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authorize via Telegram",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token, user_id = result

    # Получаем информацию о пользователе для ответа
    from app.repositories.user_repository import UserRepository
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    return TokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=900,  # 15 минут
        user_id=user_id,
        full_name=user.full_name if user else None,
        phone_number=user.phone_number if user else None
    )


@admin_router.post("/register", response_model=TokensResponse)
async def admin_register(
    request: Request,
    payload: AdminRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Регистрация администратора по email/password (без ограничений).
    """
    await rate_limiter.check_request_limit(request, f"admin_register:{payload.email}")

    from app.repositories.user_repository import UserRepository

    user_repo = UserRepository(db)
    existing = await user_repo.get_by_email(str(payload.email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    admin_user = await user_repo.create_user(
        email=str(payload.email),
        full_name=payload.full_name or "Admin",
        role=UserRole.ADMIN.value,
        is_active=True,
        is_verified=True,
        password_hash=hash_password(payload.password),
    )

    tokens = token_service.create_tokens(
        user_id=admin_user.id,
        full_name=admin_user.full_name,
        role=admin_user.role,
        email=admin_user.email,
    )
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tokens",
        )

    access_token, refresh_token, refresh_token_id, expires_at = tokens
    from app.repositories.token_repository import TokenRepository
    token_repo = TokenRepository(db)
    await token_repo.create_refresh_token(
        user_id=admin_user.id,
        token=refresh_token_id,
        expires_at=expires_at,
    )

    return TokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=900,
        user_id=admin_user.id,
        full_name=admin_user.full_name,
        email=admin_user.email,
    )


@admin_router.post("/login", response_model=TokensResponse)
async def admin_login(
    request: Request,
    payload: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Вход администратора по email/password (без ограничений).
    """
    await rate_limiter.check_request_limit(request, f"admin_login:{payload.email}")

    from app.repositories.user_repository import UserRepository

    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(str(payload.email))
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an admin",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tokens = token_service.create_tokens(
        user_id=user.id,
        full_name=user.full_name,
        role=user.role,
        email=user.email,
        phone_number=user.phone_number,
    )
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tokens",
        )

    access_token, refresh_token, refresh_token_id, expires_at = tokens
    from app.repositories.token_repository import TokenRepository
    token_repo = TokenRepository(db)
    await token_repo.create_refresh_token(
        user_id=user.id,
        token=refresh_token_id,
        expires_at=expires_at,
    )

    return TokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=900,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
    )


@router.post("/refresh", response_model=TokensResponse)
async def refresh_tokens(
        request: Request,
        token_request: RefreshTokenRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Обновление access token с помощью refresh token.
    """
    await rate_limiter.check_request_limit(request)

    auth_service = AuthService(db)
    result = await auth_service.refresh_tokens(token_request.refresh_token)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, refresh_token, user_id = result

    return TokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=900
    )


@router.post("/logout")
async def logout(
        request: Request,
        token_request: RefreshTokenRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Выход из системы (инвалидация refresh token).
    """
    await rate_limiter.check_request_limit(request)

    auth_service = AuthService(db)
    success = await auth_service.logout(token_request.refresh_token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token"
        )

    return {"message": "Successfully logged out"}


@router.get("/verify")
async def verify_token(
    current_user = Depends(get_current_user)
):
    """
    Верификация токена (для других сервисов)
    Возвращает информацию о пользователе
    """
    from app.models.user import User
    
    if isinstance(current_user, User):
        return {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "phone_number": current_user.phone_number,
            "email": current_user.email,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "is_verified": current_user.is_verified
        }
    
    # Если это dict (из token_service)
    return current_user