from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from app.core.database import get_db
from app.repositories.complaint_repository import ComplaintRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.complaint import (
    ComplaintCreate, ComplaintResponse, ComplaintStatusUpdate
)
from app.models.complaint import ComplaintStatus
from app.api.v1.endpoints.orders import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/orders/{order_id}/complaint", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED, tags=["Complaints"])
async def create_complaint(
    order_id: int,
    complaint_data: ComplaintCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Создать жалобу на заказ"""
    user = current_user
    user_id = user["id"]
    user_role = user.get("role")
    
    # Проверяем, что заказ существует и пользователь имеет к нему отношение
    order_repo = OrderRepository(db)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Проверяем права: пассажир или водитель могут жаловаться только на свои заказы
    if user_role not in ["admin", "dispatcher"]:
        if user_role == "driver" and order.driver_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create complaints for your own orders"
            )
        elif user_role == "passenger" and order.passenger_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create complaints for your own orders"
            )
    
    # Проверяем, что заказ завершен или отменен (нельзя жаловаться на активные заказы)
    from app.models.order import OrderStatus
    if order.status not in [OrderStatus.COMPLETED, OrderStatus.CANCELLED, 
                            OrderStatus.CANCELLED_BY_DRIVER, OrderStatus.CANCELLED_BY_PASSENGER]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complaints can only be created for completed or cancelled orders"
        )
    
    complaint_repo = ComplaintRepository(db)
    complaint = await complaint_repo.create_complaint(
        order_id=order_id,
        complained_by=user_id,
        complaint_data=complaint_data
    )
    
    logger.info(f"Complaint {complaint.id} created for order {order_id} by user {user_id}")
    
    return complaint


@router.get("/", response_model=List[ComplaintResponse], tags=["Complaints"])
async def get_complaints(
    status_filter: Optional[ComplaintStatus] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """Получить список всех жалоб (только для админов)"""
    complaint_repo = ComplaintRepository(db)
    complaints = await complaint_repo.get_all_complaints(
        status=status_filter,
        limit=limit,
        offset=offset
    )
    
    return complaints


@router.get("/{complaint_id}", response_model=ComplaintResponse, tags=["Complaints"])
async def get_complaint(
    complaint_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Получить детали жалобы"""
    user = current_user
    user_role = user.get("role")
    
    complaint_repo = ComplaintRepository(db)
    complaint = await complaint_repo.get_complaint_by_id(complaint_id)
    
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    
    # Проверяем права доступа
    if user_role not in ["admin", "dispatcher"]:
        if complaint.complained_by != user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own complaints"
            )
    
    return complaint


@router.patch("/{complaint_id}/status", response_model=ComplaintResponse, tags=["Complaints"])
async def update_complaint_status(
    complaint_id: int,
    status_update: ComplaintStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """Изменить статус жалобы (только для админов)"""
    complaint_repo = ComplaintRepository(db)
    complaint = await complaint_repo.get_complaint_by_id(complaint_id)
    
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    
    updated_complaint = await complaint_repo.update_complaint_status(
        complaint_id=complaint_id,
        status=status_update.status,
        resolved_by=current_user["id"],
        resolution_notes=status_update.resolution_notes
    )
    
    if not updated_complaint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update complaint status"
        )
    
    logger.info(f"Complaint {complaint_id} status updated to {status_update.status} by admin {current_user['id']}")
    
    return updated_complaint

