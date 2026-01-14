"""
Утилиты для работы с геолокацией
Расчет расстояний, времени в пути, маршрутов
"""
import math
from typing import Tuple, Optional


def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    """
    Рассчитать расстояние между двумя точками по формуле Haversine
    Возвращает расстояние в километрах
    
    Args:
        lat1: Широта первой точки
        lon1: Долгота первой точки
        lat2: Широта второй точки
        lon2: Долгота второй точки
    
    Returns:
        Расстояние в километрах
    """
    # Радиус Земли в километрах
    R = 6371.0
    
    # Преобразуем градусы в радианы
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    # Формула Haversine
    a = (
        math.sin(dlat / 2) ** 2 +
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    
    distance = R * c
    return distance


def estimate_travel_time(
    distance_km: float,
    avg_speed_kmh: float = 40.0
) -> int:
    """
    Оценить время в пути в минутах
    
    Args:
        distance_km: Расстояние в километрах
        avg_speed_kmh: Средняя скорость в км/ч (по умолчанию 40)
    
    Returns:
        Время в минутах
    """
    if distance_km <= 0:
        return 0
    
    time_hours = distance_km / avg_speed_kmh
    time_minutes = int(time_hours * 60)
    
    # Минимум 1 минута
    return max(1, time_minutes)


def calculate_route_time(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    avg_speed_kmh: float = 40.0
) -> Tuple[float, int]:
    """
    Рассчитать расстояние и время маршрута
    
    Args:
        start_lat: Широта начала маршрута
        start_lon: Долгота начала маршрута
        end_lat: Широта конца маршрута
        end_lon: Долгота конца маршрута
        avg_speed_kmh: Средняя скорость в км/ч
    
    Returns:
        Tuple (расстояние_в_км, время_в_минутах)
    """
    distance = calculate_distance(start_lat, start_lon, end_lat, end_lon)
    time_minutes = estimate_travel_time(distance, avg_speed_kmh)
    
    return distance, time_minutes


def is_point_in_radius(
    center_lat: float,
    center_lon: float,
    point_lat: float,
    point_lon: float,
    radius_km: float
) -> bool:
    """
    Проверить, находится ли точка в радиусе от центра
    
    Args:
        center_lat: Широта центра
        center_lon: Долгота центра
        point_lat: Широта точки
        point_lon: Долгота точки
        radius_km: Радиус в километрах
    
    Returns:
        True если точка в радиусе, False иначе
    """
    distance = calculate_distance(center_lat, center_lon, point_lat, point_lon)
    return distance <= radius_km


def find_nearest_point(
    target_lat: float,
    target_lon: float,
    points: list[Tuple[float, float, any]]
) -> Optional[Tuple[any, float]]:
    """
    Найти ближайшую точку к целевой
    
    Args:
        target_lat: Широта целевой точки
        target_lon: Долгота целевой точки
        points: Список точек в формате [(lat, lon, data), ...]
    
    Returns:
        Tuple (data, distance_km) или None если список пуст
    """
    if not points:
        return None
    
    min_distance = float('inf')
    nearest_point = None
    
    for lat, lon, data in points:
        distance = calculate_distance(target_lat, target_lon, lat, lon)
        if distance < min_distance:
            min_distance = distance
            nearest_point = data
    
    return nearest_point, min_distance


