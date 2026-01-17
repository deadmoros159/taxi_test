from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import httpx
import logging

from app.core.database import get_db
from app.core.config import settings
from app.repositories.order_repository import OrderRepository
from app.repositories.driver_debt_repository import DriverDebtRepository
from app.services.order_service import OrderService
from app.services.websocket_manager import websocket_manager
from app.schemas.order import OrderCreate, OrderResponse, OrderCancel, OrderAccept
from app.models.order import OrderStatus

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


async def verify_token(token: str) -> dict:
    """Проверить токен через auth-service"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Получить текущего пользователя из токена (защищенный dependency)"""
    token = credentials.credentials
    user_data = await verify_token(token)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Сохраняем токен для дальнейшего использования
    user_data["token"] = token
    
    return user_data


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Создать новый заказ (требуется авторизация)"""
    user = current_user
    
    if not user.get("is_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be verified to create orders"
        )
    
    order_repo = OrderRepository(db)
    debt_repo = DriverDebtRepository(db)
    order_service = OrderService(order_repo, debt_repo)
    
    order = await order_service.create_order(order_data, user["id"])
    
    # Отправляем уведомление водителям через WebSocket
    await websocket_manager.broadcast_new_order(order)
    
    return order


@router.get("/pending", response_model=List[OrderResponse])
async def get_pending_orders(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Получить список ожидающих заказов (для водителей, требуется авторизация)"""
    user = current_user
    
    if user.get("role") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can view pending orders"
        )
    
    order_repo = OrderRepository(db)
    orders = await order_repo.get_pending_orders()
    return orders


@router.post("/{order_id}/accept", response_model=OrderResponse)
async def accept_order(
    order_id: int,
    accept_data: OrderAccept,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Принять заказ водителем (требуется авторизация)"""
    user = current_user
    
    if user.get("role") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can accept orders"
        )
    
    # Получаем информацию о машине водителя через driver-service
    async with httpx.AsyncClient() as client:
        try:
            # Используем токен из current_user
            token = user.get("token", "")
            
            driver_response = await client.get(
                f"{settings.DRIVER_SERVICE_URL}/api/v1/drivers/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if driver_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Driver not found"
                )
            driver_data = driver_response.json()
            vehicle_info = f"{driver_data.get('vehicle', {}).get('brand', '')} {driver_data.get('vehicle', {}).get('model', '')} {driver_data.get('vehicle', {}).get('license_plate', '')}"
        except Exception as e:
            logger.error(f"Error fetching driver info: {e}")
            vehicle_info = "Unknown"
    
    order_repo = OrderRepository(db)
    debt_repo = DriverDebtRepository(db)
    order_service = OrderService(order_repo, debt_repo)
    
    order = await order_service.accept_order(
        order_id=order_id,
        driver_id=user["id"],
        accept_data=accept_data,
        vehicle_info=vehicle_info
    )
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot accept order. Order may not exist, already taken, or driver is blocked."
        )
    
    # Отправляем обновление пассажиру
    await websocket_manager.send_order_update(order)
    # Уведомляем других водителей
    await websocket_manager.send_order_accepted(order)
    
    return order


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: int,
    cancel_data: OrderCancel,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Отменить заказ (требуется авторизация)"""
    user = current_user
    
    order_repo = OrderRepository(db)
    debt_repo = DriverDebtRepository(db)
    order_service = OrderService(order_repo, debt_repo)
    
    is_driver = user.get("role") == "driver"
    
    order = await order_service.cancel_order(
        order_id=order_id,
        reason=cancel_data.reason,
        user_id=user["id"],
        is_driver=is_driver
    )
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel order. Order may not exist or you don't have permission."
        )
    
    # Отправляем обновление через WebSocket
    await websocket_manager.send_order_update(order)
    
    return order


@router.post("/{order_id}/complete", response_model=OrderResponse)
async def complete_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Завершить заказ (только для водителей, требуется авторизация)"""
    user = current_user
    
    if user.get("role") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can complete orders"
        )
    
    order_repo = OrderRepository(db)
    debt_repo = DriverDebtRepository(db)
    order_service = OrderService(order_repo, debt_repo)
    
    order = await order_service.complete_order(order_id, user["id"])
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete order"
        )
    
    await websocket_manager.send_order_update(order)
    
    return order


@router.get("/my-orders", response_model=List[OrderResponse])
async def get_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Получить мои заказы (требуется авторизация)"""
    user = current_user
    
    order_repo = OrderRepository(db)
    
    if user.get("role") == "driver":
        orders = await order_repo.get_orders_by_driver(user["id"])
    else:
        orders = await order_repo.get_orders_by_passenger(user["id"])
    
    return orders


@router.get("/all", response_model=List[OrderResponse])
async def get_all_orders(
    status: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Получить все заказы (только для админов и диспетчеров, требуется авторизация)"""
    user = current_user
    
    if user.get("role") not in ["admin", "dispatcher"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and dispatchers can view all orders"
        )
    
    order_repo = OrderRepository(db)
    
    order_status = None
    if status:
        try:
            order_status = OrderStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )
    
    orders = await order_repo.get_all_orders(limit=limit, status=order_status)
    return orders


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Получить информацию о заказе (требуется авторизация)"""
    user = current_user
    
    order_repo = OrderRepository(db)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Проверяем права доступа
    if user.get("role") not in ["admin", "dispatcher"]:
        if user.get("role") == "driver":
            if order.driver_id != user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        else:
            if order.passenger_id != user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
    
    return order


# WebSocket endpoints
@router.websocket("/ws/driver/{driver_id}")
async def websocket_driver_endpoint(websocket: WebSocket, driver_id: int):
    """WebSocket для водителей (уведомления о новых заказах)"""
    await websocket_manager.connect_driver(websocket, driver_id)
    try:
        while True:
            # Heartbeat
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await websocket_manager.disconnect_driver(websocket, driver_id)


@router.websocket("/ws/order/{order_id}")
async def websocket_order_endpoint(websocket: WebSocket, order_id: int):
    """WebSocket для заказа (обновления для пассажира)"""
    await websocket_manager.connect_order(websocket, order_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await websocket_manager.disconnect_order(websocket, order_id)

