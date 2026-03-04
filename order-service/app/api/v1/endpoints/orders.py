from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict
from datetime import datetime
import httpx
import logging

from app.core.database import get_db, AsyncSessionLocal
from app.core.config import settings
from app.repositories.order_repository import OrderRepository
from app.repositories.driver_debt_repository import DriverDebtRepository
from app.services.order_service import OrderService
from app.services.websocket_manager import websocket_manager
from app.schemas.order import (
    OrderCreate, OrderResponse, OrderCancel, OrderAccept,
    OrderStatusUpdate, OrderDetailAdminResponse, OrderLocationUpdate, OrderCompleteData
)
from app.services.pricing_service import calculate_price, calculate_estimated_price, calculate_distance
from app.models.order import Order, OrderStatus

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
    
    user_data["token"] = token
    return user_data


async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """Проверка что пользователь является админом"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this endpoint"
        )
    return current_user


async def get_user_info(user_id: int, token: str) -> Optional[dict]:
    """Получить информацию о пользователе из auth-service (требуется токен админа)"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/users/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Failed to fetch user {user_id}: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching user info for user_id {user_id}: {e}")
            return None


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, tags=["Orders"])
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
    
    await websocket_manager.broadcast_new_order(order)
    
    return order


@router.get("/active", response_model=List[OrderResponse], tags=["Orders"])
async def get_active_orders(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Получить список активных заказов (заказы со статусом PENDING, которые водитель может брать).
    Доступно для водителей.
    """
    user = current_user
    
    if user.get("role") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can view active orders"
        )
    
    order_repo = OrderRepository(db)
    return await order_repo.get_active_orders_for_drivers()


@router.get("/scheduled", response_model=List[OrderResponse], tags=["Scheduled Orders"])
async def get_scheduled_orders(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Отложенные заказы: пользователь создал заказ на будущее время.
    Доступно для водителей (чтобы выбрать заказ заранее).
    """
    if current_user.get("role") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can view scheduled orders"
        )
    order_repo = OrderRepository(db)
    return await order_repo.get_scheduled_orders_for_drivers()


@router.post("/{order_id}/accept", response_model=OrderResponse, tags=["Orders"])
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
    
    async with httpx.AsyncClient() as client:
        try:
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
    
    await websocket_manager.send_order_update(order)
    await websocket_manager.send_order_accepted(order)
    
    return order


@router.post("/{order_id}/cancel", response_model=OrderResponse, tags=["Orders"])
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
    
    await websocket_manager.send_order_update(order)
    
    return order


@router.post("/{order_id}/arrived", response_model=OrderResponse, tags=["Orders"])
async def driver_arrived(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Водитель прибыл к точке отправления (только для водителей)"""
    user = current_user
    
    if user.get("role") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can mark arrival"
        )
    
    order_repo = OrderRepository(db)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if order.driver_id != user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only mark arrival for your own orders"
        )
    
    if order.status != OrderStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot mark arrival for order with status {order.status}"
        )
    
    updated_order = await order_repo.update_order_status(
        order_id=order_id,
        status=OrderStatus.DRIVER_ARRIVED
    )
    
    if not updated_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update order status"
        )
    
    await websocket_manager.send_order_update(updated_order)
    
    return updated_order


@router.post("/{order_id}/start", response_model=OrderResponse, tags=["Orders"])
async def start_trip(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Начать поездку (только для водителей)"""
    user = current_user
    
    if user.get("role") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can start trips"
        )
    
    order_repo = OrderRepository(db)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if order.driver_id != user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only start your own orders"
        )
    
    if order.status != OrderStatus.DRIVER_ARRIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start trip for order with status {order.status}"
        )
    
    updated_order = await order_repo.update_order_status(
        order_id=order_id,
        status=OrderStatus.IN_PROGRESS
    )
    
    if not updated_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update order status"
        )
    
    await websocket_manager.send_order_update(updated_order)
    
    return updated_order


@router.post("/{order_id}/location", response_model=OrderResponse, tags=["Orders"])
async def update_driver_location(
    order_id: int,
    location_data: OrderLocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Обновить местоположение водителя (только для водителей во время активного заказа)"""
    user = current_user
    
    if user.get("role") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can update location"
        )
    
    order_repo = OrderRepository(db)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if order.driver_id != user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update location for your own orders"
        )
    
    if order.status not in [OrderStatus.ACCEPTED, OrderStatus.DRIVER_ARRIVED, OrderStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot update location for order with status {order.status}"
        )
    
    import json
    from datetime import datetime as dt
    route_history = order.route_history or "[]"
    try:
        route_points = json.loads(route_history)
    except:
        route_points = []
    
    route_points.append({
        "lat": location_data.latitude,
        "lng": location_data.longitude,
        "timestamp": dt.utcnow().isoformat()
    })
    
    updated_order = await order_repo.update_driver_location(
        order_id=order_id,
        latitude=location_data.latitude,
        longitude=location_data.longitude,
        route_history=json.dumps(route_points)
    )
    
    if not updated_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update location"
        )
    
    await websocket_manager.send_order_update(updated_order)
    
    return updated_order


@router.post("/{order_id}/complete", response_model=OrderResponse, tags=["Orders"])
async def complete_order(
    order_id: int,
    complete_data: Optional[OrderCompleteData] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Завершить заказ с расчетом финальной цены (только для водителей)"""
    user = current_user
    
    if user.get("role") != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can complete orders"
        )
    
    order_repo = OrderRepository(db)
    debt_repo = DriverDebtRepository(db)
    order_service = OrderService(order_repo, debt_repo)
    
    order = await order_service.complete_order(order_id, user["id"], complete_data)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete order"
        )
    
    await websocket_manager.send_order_update(order)
    
    return order


@router.get("/estimate-price", tags=["Orders"])
async def estimate_order_price(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
    current_user: dict = Depends(get_current_user)
):
    """
    Предварительная оценка цены по координатам (до создания заказа).
    Использует OSRM для точного расстояния по дорогам.
    """
    price, distance = await calculate_estimated_price(
        start_lat, start_lng, end_lat, end_lng
    )
    return {
        "estimated_price": price,
        "estimated_distance_km": distance,
        "currency": settings.CURRENCY,
    }


@router.get("/{order_id}/price", tags=["Orders"])
async def get_order_price(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Получить или пересчитать цену заказа"""
    order_repo = OrderRepository(db)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    user = current_user
    user_role = user.get("role")
    user_id = user.get("id")
    
    if user_role not in ["admin", "dispatcher"]:
        if user_role == "driver" and order.driver_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view price for your own orders"
            )
        elif user_role == "passenger" and order.passenger_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view price for your own orders"
            )
    
    # Если заказ завершен и есть фактические данные, используем их
    if order.status == OrderStatus.COMPLETED and order.actual_distance_km:
        price = calculate_price(
            order.actual_distance_km,
            order.actual_time_minutes
        )
        return {
            "order_id": order_id,
            "price": price,
            "distance_km": order.actual_distance_km,
            "time_minutes": order.actual_time_minutes,
            "is_final": True
        }
    
    # Иначе рассчитываем предварительную цену (OSRM или haversine)
    if order.end_latitude and order.end_longitude:
        price, distance = await calculate_estimated_price(
            order.start_latitude,
            order.start_longitude,
            order.end_latitude,
            order.end_longitude
        )
        return {
            "order_id": order_id,
            "price": price,
            "estimated_distance_km": distance,
            "estimated_time_minutes": order.estimated_time_minutes,
            "is_final": False
        }
    
    return {
        "order_id": order_id,
        "price": settings.MINIMUM_FARE,
        "is_final": False,
        "note": "End location not specified, using minimum fare"
    }


@router.get("/my-orders", response_model=List[OrderResponse], tags=["Orders"])
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


@router.get("/all", response_model=List[OrderResponse], tags=["Order Management"])
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


@router.get("/{order_id}", response_model=OrderResponse, tags=["Orders"])
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Получить информацию о заказе (требуется авторизация).
    Админ видит все заказы, водитель - только свои, пассажир - только свои.
    """
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


@router.get("/{order_id}/admin", response_model=OrderDetailAdminResponse, tags=["Order Management"])
async def get_order_detail_admin(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Получить детальную информацию о заказе (только для админа).
    Включает полную информацию о пассажире и водителе.
    """
    order_repo = OrderRepository(db)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    passenger_info = None
    if order.passenger_id:
        passenger_info = await get_user_info(order.passenger_id, current_user["token"])
    
    driver_info = None
    if order.driver_id:
        driver_info = await get_user_info(order.driver_id, current_user["token"])
    
    return OrderDetailAdminResponse(
        id=order.id,
        status=order.status,
        price=order.price,
        estimated_time_minutes=order.estimated_time_minutes,
        start_latitude=order.start_latitude,
        start_longitude=order.start_longitude,
        start_address=order.start_address,
        end_latitude=order.end_latitude,
        end_longitude=order.end_longitude,
        end_address=order.end_address,
        vehicle_info=order.vehicle_info,
        cancellation_reason=order.cancellation_reason,
        created_at=order.created_at,
        updated_at=order.updated_at,
        accepted_at=order.accepted_at,
        completed_at=order.completed_at,
        cancelled_at=order.cancelled_at,
        passenger_id=order.passenger_id,
        passenger_full_name=passenger_info.get("full_name") if passenger_info else None,
        passenger_phone=passenger_info.get("phone_number") if passenger_info else None,
        passenger_email=passenger_info.get("email") if passenger_info else None,
        driver_id=order.driver_id,
        driver_full_name=driver_info.get("full_name") if driver_info else None,
        driver_phone=driver_info.get("phone_number") if driver_info else None,
        driver_email=driver_info.get("email") if driver_info else None,
        driver_location_lat=order.driver_location_lat,
        driver_location_lng=order.driver_location_lng,
    )


@router.patch("/{order_id}/status", response_model=OrderResponse, tags=["Order Management"])
async def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Изменить статус заказа (требуется авторизация).
    Доступно для админов, диспетчеров и водителей (для своих заказов).
    """
    user = current_user
    user_role = user.get("role")
    
    order_repo = OrderRepository(db)
    order = await order_repo.get_order_by_id(order_id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Проверяем права доступа
    if user_role not in ["admin", "dispatcher"]:
        if user_role == "driver":
            # Водитель может менять статус только своих заказов
            if order.driver_id != user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only update status of your own orders"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins, dispatchers, and drivers can update order status"
            )
    
    updated_order = await order_repo.update_order_status(
        order_id=order_id,
        status=status_update.status
    )
    
    if not updated_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update order status"
        )
    
    await websocket_manager.send_order_update(updated_order)
    
    return updated_order


@router.get("/history", response_model=List[OrderResponse], tags=["Orders"])
async def get_order_history(
    status_filter: Optional[OrderStatus] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    driver_id: Optional[int] = None,
    passenger_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Получить историю заказов с фильтрацией"""
    user = current_user
    user_role = user.get("role")
    user_id = user["id"]
    
    order_repo = OrderRepository(db)
    
    if user_role not in ["admin", "dispatcher"]:
        if user_role == "driver":
            driver_id = user_id
        elif user_role == "passenger":
            passenger_id = user_id
    
    from datetime import datetime
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use ISO format (e.g., 2025-02-02T00:00:00Z)"
            )
    
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use ISO format (e.g., 2025-02-02T23:59:59Z)"
            )
    
    from sqlalchemy import select, and_
    stmt = select(Order)
    
    conditions = []
    
    if status_filter:
        conditions.append(Order.status == status_filter)
    
    if driver_id:
        conditions.append(Order.driver_id == driver_id)
    
    if passenger_id:
        conditions.append(Order.passenger_id == passenger_id)
    
    if start_dt:
        conditions.append(Order.created_at >= start_dt)
    
    if end_dt:
        conditions.append(Order.created_at <= end_dt)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(Order.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    orders = list(result.scalars().all())
    
    return orders


# WebSocket endpoints
@router.websocket("/ws/driver/{driver_id}")
async def websocket_driver_endpoint(
    websocket: WebSocket,
    driver_id: int
):
    """
    WebSocket для водителей (уведомления о новых заказах).
    
    Требуется авторизация через Bearer токен в заголовке Authorization: Bearer {token}
    Водитель может подписаться только на свои уведомления.
    """
    # Принимаем соединение
    await websocket.accept()
    
    # Получаем токен из заголовка Authorization
    auth_header = websocket.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token required in Authorization header")
        return
    
    # Извлекаем токен
    token = auth_header[7:]  # Убираем "Bearer "
    
    # Проверяем токен
    user_data = await verify_token(token)
    if not user_data:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    user_role = user_data.get("role")
    user_id = user_data.get("id")
    
    if user_role != "driver":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Only drivers can connect")
        return
    
    if user_id != driver_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Access denied: can only subscribe to your own notifications")
        return

    await websocket_manager.connect_driver(websocket, driver_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await websocket_manager.disconnect_driver(websocket, driver_id)


@router.websocket("/ws/order/{order_id}")
async def websocket_order_endpoint(
    websocket: WebSocket,
    order_id: int
):
    """
    WebSocket для заказа (обновления для пассажира, водителя или админа).
    
    Требуется авторизация через Bearer токен в заголовке Authorization: Bearer {token}
    Пользователь может подписаться только на свои заказы (пассажир - на свои, водитель - на свои, админ - на любые).
    """
    # Принимаем соединение
    await websocket.accept()
    
    # Получаем токен из заголовка Authorization
    auth_header = websocket.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token required in Authorization header")
        return
    
    # Извлекаем токен
    token = auth_header[7:]  # Убираем "Bearer "
    
    # Проверяем токен
    user_data = await verify_token(token)
    if not user_data:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return
    
    # Проверяем права доступа
    user_role = user_data.get("role")
    user_id = user_data.get("id")
    
    # Админы и диспетчеры могут подписаться на любые заказы
    if user_role not in ["admin", "dispatcher"]:
        # Получаем информацию о заказе для проверки прав
        async with AsyncSessionLocal() as db_session:
            order_repo = OrderRepository(db_session)
            order = await order_repo.get_order_by_id(order_id)
            
            if not order:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Order not found")
                return
            
            # Проверяем, что пользователь имеет отношение к заказу
            if user_role == "driver":
                if order.driver_id != user_id:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Access denied: can only subscribe to your own orders")
                    return
            else:  # passenger
                if order.passenger_id != user_id:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Access denied: can only subscribe to your own orders")
                    return
    
    # Подключаем к заказу
    await websocket_manager.connect_order(websocket, order_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await websocket_manager.disconnect_order(websocket, order_id)


@router.get("/ws/info", tags=["WebSocket"])
async def websocket_info():
    """WebSocket эндпоинты: ws/driver/{driver_id}, ws/order/{order_id}. Auth: Bearer в заголовке."""
    return {
        "websocket_endpoints": {
            "driver_notifications": {
                "path": "/api/v1/orders/ws/driver/{driver_id}",
                "description": "WebSocket для водителей - уведомления о новых заказах",
                "authentication": "Bearer token в заголовке Authorization",
                "access": "Только водители, только свои уведомления",
                "message_types": ["new_order", "order_accepted"]
            },
            "order_updates": {
                "path": "/api/v1/orders/ws/order/{order_id}",
                "description": "WebSocket для обновлений по конкретному заказу",
                "authentication": "Bearer token в заголовке Authorization",
                "access": "Пассажиры - свои заказы, водители - свои заказы, админы - любые",
                "message_types": ["order_update"]
            }
        },
        "note": "WebSocket эндпоинты используют протокол WebSocket и не отображаются в REST API документации"
    }

