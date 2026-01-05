from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.auth import PhoneAuthRequest, VerifyCodeRequest, TokensResponse
from app.schemas.token import RefreshTokenRequest
from app.services.auth_service import AuthService
from app.utils.rate_limiter import rate_limiter

router = APIRouter()


@router.post("/request-code", response_model=dict)
async def request_sms_code(
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


@router.post("/verify-code", response_model=TokensResponse)
async def verify_sms_code(
        request: Request,
        verify_request: VerifyCodeRequest,
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
        full_name=user.full_name if user else None
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