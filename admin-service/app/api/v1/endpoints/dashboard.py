"""
Эндпоинты для админ-дашборда
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime
import httpx
import logging

from app.core.config import settings
from app.services.stats_service import StatsService
from app.services.aggregation_service import AggregationService

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Проверить токен админа через auth-service (защищенный dependency)"""
    token = credentials.credentials
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code == 200:
                user_data = response.json()
                # Проверяем, что это админ или диспетчер
                role = user_data.get("role")
                if role not in ["admin", "dispatcher"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied. Admin or dispatcher role required."
                    )
                # Сохраняем токен для дальнейшего использования
                user_data["token"] = token
                return user_data
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except httpx.HTTPError as e:
            logger.error(f"Error verifying token: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable"
            )


@router.get("/stats")
async def get_dashboard_stats(
    current_user: dict = Depends(verify_admin_token)
):
    """
    Получить общую статистику для дашборда
    Доступно только для админов и диспетчеров (требуется авторизация)
    """
    user = current_user
    
    stats_service = StatsService()
    stats = await stats_service.get_dashboard_stats(user.get("token", ""))
    
    return stats


@router.get("/orders/stats")
async def get_orders_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(verify_admin_token)
):
    """
    Получить статистику по заказам за период
    Доступно только для админов и диспетчеров (требуется авторизация)
    """
    user = current_user
    
    start = None
    end = None
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO format."
            )
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO format."
            )
    
    stats_service = StatsService()
    stats = await stats_service.get_orders_stats(
        user.get("token", ""),
        start_date=start,
        end_date=end
    )
    
    return stats


@router.get("/drivers/stats")
async def get_drivers_stats(
    current_user: dict = Depends(verify_admin_token)
):
    """
    Получить статистику по водителям
    Доступно только для админов и диспетчеров (требуется авторизация)
    """
    user = current_user
    
    stats_service = StatsService()
    stats = await stats_service.get_drivers_stats(user.get("token", ""))
    
    return stats




