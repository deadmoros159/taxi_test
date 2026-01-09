from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.auth import (
    PhoneAuthRequest, 
    EmailAuthRequest,
    VerifyCodeRequest, 
    VerifyPhoneCodeRequest,
    VerifyEmailCodeRequest,
    TokensResponse
)
from app.schemas.token import RefreshTokenRequest
from app.services.auth_service import AuthService
from app.utils.rate_limiter import rate_limiter
from app.api.v1.dependencies import get_current_user

router = APIRouter()

# Подроутеры для phone и email
phone_router = APIRouter()
email_router = APIRouter()


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