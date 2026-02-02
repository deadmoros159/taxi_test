from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from app.models.complaint import Complaint, ComplaintStatus
from app.schemas.complaint import ComplaintCreate
import logging

logger = logging.getLogger(__name__)


class ComplaintRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_complaint(
        self,
        order_id: int,
        complained_by: int,
        complaint_data: ComplaintCreate
    ) -> Complaint:
        """Создать жалобу"""
        complaint = Complaint(
            order_id=order_id,
            complained_by=complained_by,
            complaint_type=complaint_data.complaint_type,
            description=complaint_data.description,
            media_ids=complaint_data.media_ids,
            status=ComplaintStatus.PENDING
        )
        
        self.db.add(complaint)
        await self.db.commit()
        await self.db.refresh(complaint)
        
        return complaint

    async def get_complaint_by_id(self, complaint_id: int) -> Optional[Complaint]:
        """Получить жалобу по ID"""
        result = await self.db.execute(
            select(Complaint).where(Complaint.id == complaint_id)
        )
        return result.scalar_one_or_none()

    async def get_complaints_by_order(self, order_id: int) -> List[Complaint]:
        """Получить все жалобы по заказу"""
        result = await self.db.execute(
            select(Complaint).where(Complaint.order_id == order_id)
            .order_by(Complaint.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_all_complaints(
        self,
        status: Optional[ComplaintStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Complaint]:
        """Получить все жалобы (для админов)"""
        stmt = select(Complaint)
        if status:
            stmt = stmt.where(Complaint.status == status)
        stmt = stmt.order_by(Complaint.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_complaint_status(
        self,
        complaint_id: int,
        status: ComplaintStatus,
        resolved_by: int,
        resolution_notes: Optional[str] = None
    ) -> Optional[Complaint]:
        """Обновить статус жалобы"""
        from datetime import datetime
        
        complaint = await self.get_complaint_by_id(complaint_id)
        if not complaint:
            return None
        
        complaint.status = status
        complaint.resolved_by = resolved_by
        if resolution_notes:
            complaint.resolution_notes = resolution_notes
        
        if status in [ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED]:
            complaint.resolved_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(complaint)
        
        return complaint

