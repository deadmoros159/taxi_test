from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
import json
import logging
from app.models.order import Order

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Менеджер WebSocket соединений для уведомлений водителей"""
    
    def __init__(self):
        # Словарь: driver_id -> Set[WebSocket]
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Словарь: order_id -> Set[WebSocket] (для пассажиров)
        self.order_connections: Dict[int, Set[WebSocket]] = {}

    async def connect_driver(self, websocket: WebSocket, driver_id: int):
        """Подключить водителя"""
        await websocket.accept()
        if driver_id not in self.active_connections:
            self.active_connections[driver_id] = set()
        self.active_connections[driver_id].add(websocket)
        logger.info(f"Driver {driver_id} connected. Total connections: {len(self.active_connections[driver_id])}")

    async def disconnect_driver(self, websocket: WebSocket, driver_id: int):
        """Отключить водителя"""
        if driver_id in self.active_connections:
            self.active_connections[driver_id].discard(websocket)
            if not self.active_connections[driver_id]:
                del self.active_connections[driver_id]
        logger.info(f"Driver {driver_id} disconnected")

    async def connect_order(self, websocket: WebSocket, order_id: int):
        """Подключить к заказу (для пассажира)"""
        await websocket.accept()
        if order_id not in self.order_connections:
            self.order_connections[order_id] = set()
        self.order_connections[order_id].add(websocket)
        logger.info(f"Order {order_id} connection opened")

    async def disconnect_order(self, websocket: WebSocket, order_id: int):
        """Отключить от заказа"""
        if order_id in self.order_connections:
            self.order_connections[order_id].discard(websocket)
            if not self.order_connections[order_id]:
                del self.order_connections[order_id]

    async def broadcast_new_order(self, order: Order):
        """Отправить уведомление о новом заказе всем водителям"""
        message = {
            "type": "new_order",
            "order": {
                "id": order.id,
                "passenger_id": order.passenger_id,
                "start_latitude": order.start_latitude,
                "start_longitude": order.start_longitude,
                "start_address": order.start_address,
                "end_latitude": order.end_latitude,
                "end_longitude": order.end_longitude,
                "end_address": order.end_address,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
        }
        
        disconnected = []
        for driver_id, connections in self.active_connections.items():
            for connection in connections.copy():
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to driver {driver_id}: {e}")
                    disconnected.append((driver_id, connection))
        
        # Удаляем отключенные соединения
        for driver_id, connection in disconnected:
            await self.disconnect_driver(connection, driver_id)

    async def send_order_update(self, order: Order):
        """Отправить обновление заказа пассажиру"""
        message = {
            "type": "order_update",
            "order": {
                "id": order.id,
                "status": order.status.value,
                "driver_id": order.driver_id,
                "driver_location_lat": order.driver_location_lat,
                "driver_location_lng": order.driver_location_lng,
                "estimated_time_minutes": order.estimated_time_minutes,
                "vehicle_info": order.vehicle_info,
                "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
            }
        }
        
        if order.id in self.order_connections:
            disconnected = []
            for connection in self.order_connections[order.id].copy():
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending update for order {order.id}: {e}")
                    disconnected.append(connection)
            
            for connection in disconnected:
                await self.disconnect_order(connection, order.id)

    async def send_order_accepted(self, order: Order):
        """Отправить уведомление о принятии заказа (для других водителей)"""
        message = {
            "type": "order_accepted",
            "order_id": order.id
        }
        
        # Отправляем всем водителям, кроме того, кто принял заказ
        disconnected = []
        for driver_id, connections in self.active_connections.items():
            if driver_id == order.driver_id:
                continue
            for connection in connections.copy():
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending acceptance notification: {e}")
                    disconnected.append((driver_id, connection))
        
        for driver_id, connection in disconnected:
            await self.disconnect_driver(connection, driver_id)


# Глобальный экземпляр менеджера
websocket_manager = WebSocketManager()


