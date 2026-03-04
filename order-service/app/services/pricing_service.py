"""
Сервис расчёта цены заказа (Узбекистан, сом).
Использует OSRM для точного расстояния по дорогам, fallback — haversine с коэффициентом.
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def calculate_distance_haversine(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Рассчитать расстояние между двумя точками в километрах (формула гаверсинуса)
    
    Args:
        lat1, lon1: Координаты первой точки
        lat2, lon2: Координаты второй точки
    
    Returns:
        Расстояние в километрах
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # Радиус Земли в километрах
    R = 6371.0
    
    # Преобразуем градусы в радианы
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)
    
    # Разница координат
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    # Формула гаверсинуса
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    return distance


# Алиас для обратной совместимости
calculate_distance = calculate_distance_haversine


def calculate_price(
    distance_km: float,
    time_minutes: Optional[int] = None,
    estimated_time_minutes: Optional[int] = None
) -> float:
    """
    Рассчитать цену заказа на основе расстояния и времени
    
    Args:
        distance_km: Расстояние в километрах
        time_minutes: Фактическое время поездки в минутах (если есть)
        estimated_time_minutes: Оценочное время в минутах (если фактического нет)
    
    Returns:
        Цена заказа в сомах (UZS)
    """
    # Используем фактическое время, если есть, иначе оценочное
    time = time_minutes if time_minutes is not None else (estimated_time_minutes or 0)
    
    # Базовая стоимость
    price = settings.BASE_FARE
    
    # Добавляем стоимость за расстояние
    price += distance_km * settings.PRICE_PER_KM
    
    # Добавляем стоимость за время
    price += time * settings.PRICE_PER_MINUTE
    
    # Применяем минимальную стоимость
    price = max(price, settings.MINIMUM_FARE)
    
    # Округляем до 2 знаков после запятой
    price = round(price, 2)
    
    logger.info(
        f"Calculated price: {price} {settings.CURRENCY} (distance: {distance_km:.2f} km, "
        f"time: {time} min, base: {settings.BASE_FARE}, per_km: {settings.PRICE_PER_KM}, "
        f"per_min: {settings.PRICE_PER_MINUTE})"
    )
    
    return price


async def calculate_estimated_price(
    start_lat: float,
    start_lng: float,
    end_lat: Optional[float] = None,
    end_lng: Optional[float] = None
) -> tuple[float, Optional[float]]:
    """
    Рассчитать предварительную цену заказа на основе координат.
    Пытается получить расстояние по дорогам через OSRM, иначе haversine * коэффициент.
    
    Args:
        start_lat, start_lng: Координаты точки отправления
        end_lat, end_lng: Координаты точки назначения (опционально)
    
    Returns:
        Кортеж (цена, расстояние_в_км)
    """
    if end_lat is None or end_lng is None:
        return settings.MINIMUM_FARE, None

    distance: float
    estimated_time: int

    # Пробуем OSRM (реальное расстояние по дорогам)
    from app.services.routing_service import get_route_info

    route_info = await get_route_info(start_lat, start_lng, end_lat, end_lng)
    if route_info:
        distance, estimated_time = route_info
    else:
        # Fallback: haversine с коэффициентом (дороги длиннее прямой линии)
        haversine_km = calculate_distance_haversine(
            start_lat, start_lng, end_lat, end_lng
        )
        distance = haversine_km * settings.HAVERSINE_MULTIPLIER
        estimated_time = max(1, int(distance * 2))  # ~2 мин/км в городе

    price = calculate_price(distance, estimated_time_minutes=estimated_time)
    return price, distance


