"""
Сервис маршрутизации — получение расстояния и времени по дорогам через OSRM.
Используется для точного расчёта цены заказа (реальное расстояние по дорогам).
"""
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def get_route_info(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> Optional[tuple[float, int]]:
    """
    Получить расстояние и время маршрута по дорогам через OSRM.

    Args:
        start_lat, start_lng: Координаты точки отправления
        end_lat, end_lng: Координаты точки назначения

    Returns:
        Кортеж (distance_km, duration_minutes) или None при ошибке
    """
    if not settings.OSRM_URL:
        return None

    # OSRM использует формат lon,lat (GeoJSON)
    coords = f"{start_lng},{start_lat};{end_lng},{end_lat}"
    url = f"{settings.OSRM_URL.rstrip('/')}/route/v1/driving/{coords}?overview=false"

    try:
        async with httpx.AsyncClient(timeout=settings.OSRM_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") != "Ok":
            logger.warning(
                f"OSRM returned non-Ok: {data.get('code')}, {data.get('message', '')}"
            )
            return None

        routes = data.get("routes", [])
        if not routes:
            logger.warning("OSRM returned no routes")
            return None

        route = routes[0]
        distance_m = route.get("distance", 0)
        duration_s = route.get("duration", 0)

        distance_km = distance_m / 1000
        duration_min = max(1, int(duration_s / 60))

        logger.debug(
            f"OSRM route: {distance_km:.2f} km, {duration_min} min"
        )
        return distance_km, duration_min

    except httpx.TimeoutException:
        logger.warning("OSRM request timeout")
        return None
    except httpx.HTTPError as e:
        logger.warning(f"OSRM HTTP error: {e}")
        return None
    except Exception as e:
        logger.warning(f"OSRM error: {e}", exc_info=True)
        return None
