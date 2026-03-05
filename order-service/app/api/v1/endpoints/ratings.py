from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from app.core.database import get_db
from app.repositories.rating_repository import RatingRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.driver_debt_repository import DriverDebtRepository
from app.schemas.rating import RatingCreate, RatingResponse, RatingStatsResponse
from app.api.v1.endpoints.orders import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/orders/{order_id}/rating", response_model=RatingResponse, status_code=status.HTTP_201_CREATED, tags=["Ratings"])
async def create_rating(
    order_id: int,
    rating_data: RatingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Оставить оценку водителю за заказ (только для пассажиров)"""
    user = current_user
    user_id = user["id"]
    user_role = user.get("role")
    
    # Только пассажиры могут оценивать
    if user_role != "passenger":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only passengers can rate drivers"
        )
    
    # Проверяем, что заказ существует
    order_repo = OrderRepository(db)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Проверяем, что это заказ пассажира
    if order.passenger_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only rate your own orders"
        )
    
    # Проверяем, что заказ завершен
    from app.models.order import OrderStatus
    if order.status != OrderStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ratings can only be created for completed orders"
        )
    
    # Проверяем, что есть водитель
    if not order.driver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order has no driver to rate"
        )
    
    # Создаем оценку
    rating_repo = RatingRepository(db)
    try:
        rating = await rating_repo.create_rating(
            order_id=order_id,
            passenger_id=user_id,
            driver_id=order.driver_id,
            rating_data=rating_data
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    logger.info(f"Rating {rating.id} created for order {order_id} by passenger {user_id} for driver {order.driver_id}")
    
    return rating


@router.get("/drivers/{driver_id}/ratings", response_model=List[RatingResponse], tags=["Ratings"])
async def get_driver_ratings(
    driver_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Получить оценки водителя"""
    rating_repo = RatingRepository(db)
    ratings = await rating_repo.get_ratings_by_driver(driver_id)
    
    return ratings


@router.get("/drivers/{driver_id}/stats", response_model=RatingStatsResponse, tags=["Ratings"])
async def get_driver_rating_stats(
    driver_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Получить статистику оценок водителя"""
    rating_repo = RatingRepository(db)
    stats = await rating_repo.get_rating_stats(driver_id)
    
    return stats


@router.get("/drivers/{driver_id}/summary", tags=["Ratings"])
async def get_driver_summary(
    driver_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Сводка по водителю: рейтинг, баланс (долг к оплате), просрочка/задолженность.
    Водитель — только свои данные, админ/диспетчер — любые.
    """
    user = current_user
    user_id = user.get("id")
    role = user.get("role")

    if role not in ("admin", "dispatcher"):
        if role != "driver" or user_id != driver_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    rating_repo = RatingRepository(db)
    debt_repo = DriverDebtRepository(db)

    stats = await rating_repo.get_rating_stats(driver_id)
    unpaid = await debt_repo.get_unpaid_debts(driver_id=driver_id)

    total_remaining = sum(d.remaining_amount for d in unpaid)
    now = datetime.utcnow()
    overdue = [d for d in unpaid if d.due_date < now]
    is_blocked = any(d.is_blocked for d in unpaid)
    has_overdue = len(overdue) > 0

    return {
        "driver_id": driver_id,
        "rating": {
            "average_rating": stats["average_rating"],
            "total_ratings": stats["total_ratings"],
        },
        "balance": round(total_remaining, 2),
        "debt_info": {
            "is_blocked": is_blocked,
            "has_overdue": has_overdue,
            "overdue_count": len(overdue),
        },
    }

