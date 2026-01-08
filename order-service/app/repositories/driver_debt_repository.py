from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List
from datetime import datetime, timedelta
from app.models.driver_debt import DriverDebt
from app.schemas.driver_debt import DriverDebtCreate
import logging

logger = logging.getLogger(__name__)


class DriverDebtRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_debt(self, debt_data: DriverDebtCreate) -> DriverDebt:
        """Создать долг водителя"""
        debt = DriverDebt(
            order_id=debt_data.order_id,
            driver_id=debt_data.driver_id,
            amount=debt_data.amount,
            remaining_amount=debt_data.amount,
            due_date=debt_data.due_date,
        )
        self.db.add(debt)
        await self.db.commit()
        await self.db.refresh(debt)
        return debt

    async def get_debt_by_id(self, debt_id: int) -> Optional[DriverDebt]:
        """Получить долг по ID"""
        result = await self.db.execute(
            select(DriverDebt).where(DriverDebt.id == debt_id)
        )
        return result.scalar_one_or_none()

    async def get_debts_by_driver(self, driver_id: int) -> List[DriverDebt]:
        """Получить все долги водителя"""
        result = await self.db.execute(
            select(DriverDebt).where(DriverDebt.driver_id == driver_id)
            .order_by(DriverDebt.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_unpaid_debts(self, driver_id: Optional[int] = None) -> List[DriverDebt]:
        """Получить неоплаченные долги"""
        query = select(DriverDebt).where(DriverDebt.is_paid == False)
        if driver_id:
            query = query.where(DriverDebt.driver_id == driver_id)
        result = await self.db.execute(query.order_by(DriverDebt.due_date.asc()))
        return list(result.scalars().all())

    async def get_overdue_debts(self) -> List[DriverDebt]:
        """Получить просроченные долги"""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(DriverDebt).where(
                and_(
                    DriverDebt.is_paid == False,
                    DriverDebt.due_date < now
                )
            ).order_by(DriverDebt.due_date.asc())
        )
        return list(result.scalars().all())

    async def pay_debt(self, debt_id: int, amount: float, notes: Optional[str] = None) -> Optional[DriverDebt]:
        """Оплатить долг"""
        debt = await self.get_debt_by_id(debt_id)
        if not debt:
            return None

        debt.paid_amount += amount
        debt.remaining_amount -= amount
        
        if debt.remaining_amount <= 0:
            debt.is_paid = True
            debt.paid_at = datetime.utcnow()
            debt.is_blocked = False  # Разблокируем при полной оплате
        
        if notes:
            debt.notes = notes

        await self.db.commit()
        await self.db.refresh(debt)
        return debt

    async def block_driver(self, driver_id: int) -> List[DriverDebt]:
        """Заблокировать водителя из-за просроченных долгов"""
        overdue_debts = await self.get_overdue_debts()
        driver_debts = [d for d in overdue_debts if d.driver_id == driver_id and not d.is_blocked]
        
        now = datetime.utcnow()
        for debt in driver_debts:
            debt.is_blocked = True
            debt.blocked_at = now

        if driver_debts:
            await self.db.commit()
        
        return driver_debts

