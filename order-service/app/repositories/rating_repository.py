from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Dict
from app.models.rating import Rating
from app.schemas.rating import RatingCreate
import logging

logger = logging.getLogger(__name__)


class RatingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_rating(
        self,
        order_id: int,
        passenger_id: int,
        driver_id: int,
        rating_data: RatingCreate
    ) -> Rating:
        """Создать оценку водителя пассажиром"""
        # Проверяем, нет ли уже оценки для этого заказа
        existing = await self.get_rating_by_order_id(order_id)
        if existing:
            raise ValueError("Rating already exists for this order")
        
        rating = Rating(
            order_id=order_id,
            passenger_id=passenger_id,
            driver_id=driver_id,
            rating=rating_data.rating,
            comment=rating_data.comment
        )
        
        self.db.add(rating)
        await self.db.commit()
        await self.db.refresh(rating)
        
        return rating

    async def get_rating_by_id(self, rating_id: int) -> Optional[Rating]:
        """Получить оценку по ID"""
        result = await self.db.execute(
            select(Rating).where(Rating.id == rating_id)
        )
        return result.scalar_one_or_none()

    async def get_rating_by_order_id(self, order_id: int) -> Optional[Rating]:
        """Получить оценку по ID заказа"""
        result = await self.db.execute(
            select(Rating).where(Rating.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_ratings_by_driver(self, driver_id: int, limit: int = 50) -> List[Rating]:
        """Получить все оценки водителя"""
        result = await self.db.execute(
            select(Rating).where(Rating.driver_id == driver_id)
            .order_by(Rating.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_rating_stats(self, driver_id: int) -> Dict:
        """Получить статистику оценок водителя"""
        # Средняя оценка
        avg_result = await self.db.execute(
            select(func.avg(Rating.rating)).where(Rating.driver_id == driver_id)
        )
        average_rating = avg_result.scalar() or 0.0
        
        # Общее количество оценок
        count_result = await self.db.execute(
            select(func.count(Rating.id)).where(Rating.driver_id == driver_id)
        )
        total_ratings = count_result.scalar() or 0
        
        # Распределение по оценкам
        breakdown = {}
        for rating_value in range(1, 6):
            count_result = await self.db.execute(
                select(func.count(Rating.id)).where(
                    Rating.driver_id == driver_id,
                    Rating.rating == rating_value
                )
            )
            breakdown[rating_value] = count_result.scalar() or 0
        
        return {
            "user_id": driver_id,
            "average_rating": round(float(average_rating), 2),
            "total_ratings": total_ratings,
            "ratings_breakdown": breakdown
        }

