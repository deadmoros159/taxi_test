"""
Эндпоинты для просмотра и управления данными в БД
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()


async def verify_admin_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Проверить токен админа или диспетчера через auth-service"""
    token = credentials.credentials
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if response.status_code == 200:
                user_data = response.json()
                # Проверяем, что это админ или диспетчер
                role = user_data.get("role")
                if role not in ["admin", "dispatcher"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied. Admin or dispatcher role required."
                    )
                # Сохраняем токен для дальнейшего использования
                user_data["token"] = token
                return user_data
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except httpx.HTTPError as e:
            logger.error(f"Error verifying token: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable"
            )


def require_admin_only(current_user: dict = Depends(verify_admin_token)) -> dict:
    """Только админы могут использовать этот эндпоинт"""
    role = current_user.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required."
        )
    return current_user


# ==================== ВОДИТЕЛИ ====================

@router.get("/drivers")
async def get_drivers(
    current_user: dict = Depends(verify_admin_token)
):
    """
    Получить список всех водителей
    
    Доступ:
    - Диспетчеры: могут видеть всех водителей
    - Админы: могут видеть всех водителей
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.DRIVER_SERVICE_URL}/api/v1/admin/drivers",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 200:
                return {"drivers": response.json(), "total": len(response.json())}
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error fetching drivers: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error fetching drivers: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Driver service unavailable"
            )


@router.get("/drivers/{driver_id}")
async def get_driver(
    driver_id: int,
    current_user: dict = Depends(verify_admin_token)
):
    """
    Получить информацию о водителе по ID
    
    Доступ:
    - Диспетчеры: могут видеть всех водителей
    - Админы: могут видеть всех водителей
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.DRIVER_SERVICE_URL}/api/v1/admin/drivers/{driver_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Driver not found"
                )
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error fetching driver: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error fetching driver: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Driver service unavailable"
            )


@router.delete("/drivers/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_driver(
    driver_id: int,
    current_user: dict = Depends(verify_admin_token)
):
    """
    Удалить водителя
    
    Доступ:
    - Диспетчеры: могут удалять водителей
    - Админы: могут удалять водителей
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f"{settings.DRIVER_SERVICE_URL}/api/v1/admin/drivers/{driver_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 204:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Driver not found"
                )
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error deleting driver: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error deleting driver: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Driver service unavailable"
            )


# ==================== ПОЛЬЗОВАТЕЛИ (ПАССАЖИРЫ) ====================

@router.get("/users")
async def get_users(
    role: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(verify_admin_token)
):
    """
    Получить список пользователей
    
    Доступ:
    - Диспетчеры: могут видеть только пассажиров (role=passenger)
    - Админы: могут видеть всех пользователей (кроме сотрудников - используйте /staff)
    """
    user_role = current_user.get("role")
    token = current_user.get("token", "")
    
    # Диспетчеры могут видеть только пассажиров
    if user_role == "dispatcher":
        if role and role != "passenger":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Dispatchers can only view passengers"
            )
        role = "passenger"
    
    # Админы не могут видеть сотрудников через этот endpoint
    if user_role == "admin" and role == "dispatcher":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /staff endpoint to view dispatchers"
        )
    
    async with httpx.AsyncClient() as client:
        try:
            params = {"limit": limit, "offset": offset}
            if role:
                params["role"] = role
            
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=10.0
            )
            if response.status_code == 200:
                users = response.json()
                return {"users": users, "total": len(users)}
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error fetching users: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error fetching users: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable"
            )


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    current_user: dict = Depends(verify_admin_token)
):
    """
    Получить информацию о пользователе по ID
    
    Доступ:
    - Диспетчеры: могут видеть только пассажиров
    - Админы: могут видеть всех пользователей (кроме сотрудников)
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error fetching user: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error fetching user: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable"
            )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: dict = Depends(verify_admin_token)
):
    """
    Удалить пользователя
    
    Доступ:
    - Диспетчеры: могут удалять только пассажиров
    - Админы: могут удалять всех пользователей (кроме других админов)
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f"{settings.AUTH_SERVICE_URL}/api/v1/admin/users/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 204:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error deleting user: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error deleting user: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable"
            )


# ==================== АВТОПАРК (VEHICLES) ====================

@router.get("/vehicles")
async def get_vehicles(
    current_user: dict = Depends(verify_admin_token)
):
    """
    Получить список всех автомобилей
    
    Доступ:
    - Диспетчеры: могут видеть все автомобили
    - Админы: могут видеть все автомобили
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.DRIVER_SERVICE_URL}/api/v1/admin/vehicles",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 200:
                vehicles = response.json()
                return {"vehicles": vehicles, "total": len(vehicles)}
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error fetching vehicles: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error fetching vehicles: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Driver service unavailable"
            )


@router.get("/vehicles/{vehicle_id}")
async def get_vehicle(
    vehicle_id: int,
    current_user: dict = Depends(verify_admin_token)
):
    """
    Получить информацию об автомобиле по ID
    
    Доступ:
    - Диспетчеры: могут видеть все автомобили
    - Админы: могут видеть все автомобили
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.DRIVER_SERVICE_URL}/api/v1/admin/vehicles/{vehicle_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vehicle not found"
                )
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error fetching vehicle: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error fetching vehicle: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Driver service unavailable"
            )


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: int,
    current_user: dict = Depends(verify_admin_token)
):
    """
    Удалить автомобиль
    
    Доступ:
    - Диспетчеры: могут удалять автомобили
    - Админы: могут удалять автомобили
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f"{settings.DRIVER_SERVICE_URL}/api/v1/admin/vehicles/{vehicle_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 204:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vehicle not found"
                )
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error deleting vehicle: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error deleting vehicle: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Driver service unavailable"
            )


# ==================== СОТРУДНИКИ (STAFF) ====================

@router.get("/staff")
async def get_staff(
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(require_admin_only)
):
    """
    Получить список всех сотрудников (диспетчеры и админы)
    
    Доступ:
    - Только админы могут видеть сотрудников
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            params = {"limit": limit, "offset": offset}
            
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/admin/staff",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=10.0
            )
            if response.status_code == 200:
                staff = response.json()
                return {"staff": staff, "total": len(staff)}
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. Admin role required."
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error fetching staff: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error fetching staff: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable"
            )


@router.get("/staff/{user_id}")
async def get_staff_member(
    user_id: int,
    current_user: dict = Depends(require_admin_only)
):
    """
    Получить информацию о сотруднике по ID
    
    Доступ:
    - Только админы могут видеть сотрудников
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.AUTH_SERVICE_URL}/api/v1/admin/staff/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Staff member not found"
                )
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. Admin role required."
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error fetching staff member: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error fetching staff member: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable"
            )


@router.delete("/staff/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff_member(
    user_id: int,
    current_user: dict = Depends(require_admin_only)
):
    """
    Удалить сотрудника (диспетчера)
    
    Доступ:
    - Только админы могут удалять сотрудников
    """
    token = current_user.get("token", "")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f"{settings.AUTH_SERVICE_URL}/api/v1/admin/staff/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0
            )
            if response.status_code == 204:
                return Response(status_code=status.HTTP_204_NO_CONTENT)
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Staff member not found"
                )
            elif response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. Admin role required."
                )
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error deleting staff member: {response.text}"
                )
        except httpx.HTTPError as e:
            logger.error(f"Error deleting staff member: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth service unavailable"
            )

