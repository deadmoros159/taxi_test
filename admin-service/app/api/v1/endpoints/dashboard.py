"""
Эндпоинты для админ-дашборда
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from datetime import datetime
import httpx
import logging

from app.core.config import settings
from app.services.stats_service import StatsService
from app.services.aggregation_service import AggregationService

logger = logging.getLogger(__name__)

router = APIRouter()


async def verify_admin_token(authorization: str = None) -> dict:
    """Проверить токен админа через auth-service"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.split(" ")[1]
    
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
                return user_data
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        except httpx.HTTPError as e:
            logger.error(f"Error verifying token: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable"
            )


@router.get("/stats")
async def get_dashboard_stats(
    authorization: str = None
):
    """
    Получить общую статистику для дашборда
    Доступно только для админов и диспетчеров
    """
    user = await verify_admin_token(authorization)
    
    stats_service = StatsService()
    stats = await stats_service.get_dashboard_stats(user.get("token", authorization))
    
    return stats


@router.get("/orders/stats")
async def get_orders_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    authorization: str = None
):
    """
    Получить статистику по заказам за период
    Доступно только для админов и диспетчеров
    """
    user = await verify_admin_token(authorization)
    
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
        user.get("token", authorization),
        start_date=start,
        end_date=end
    )
    
    return stats


@router.get("/drivers/stats")
async def get_drivers_stats(
    authorization: str = None
):
    """
    Получить статистику по водителям
    Доступно только для админов и диспетчеров
    """
    user = await verify_admin_token(authorization)
    
    stats_service = StatsService()
    stats = await stats_service.get_drivers_stats(user.get("token", authorization))
    
    return stats


@router.get("/drivers")
async def get_all_drivers(
    authorization: str = None
):
    """
    Получить список всех водителей
    Доступно только для админов и диспетчеров
    """
    user = await verify_admin_token(authorization)
    
    aggregation = AggregationService()
    drivers = await aggregation.get_all_drivers(user.get("token", authorization))
    
    return {"drivers": drivers, "total": len(drivers)}


@router.get("/orders")
async def get_all_orders(
    status: Optional[str] = None,
    limit: int = 100,
    authorization: str = None
):
    """
    Получить список всех заказов
    Доступно только для админов и диспетчеров
    """
    user = await verify_admin_token(authorization)
    
    aggregation = AggregationService()
    orders = await aggregation.get_all_orders(
        user.get("token", authorization),
        status=status,
        limit=limit
    )
    
    return {"orders": orders, "total": len(orders)}


