from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from typing import Optional, List
from app.models.driver import Driver, Vehicle, DriverStatus
from app.schemas.driver import VehicleCreate
import logging

logger = logging.getLogger(__name__)


class DriverRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, driver_id: int) -> Optional[Driver]:
        stmt = select(Driver).options(selectinload(Driver.vehicle)).where(Driver.id == driver_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> Optional[Driver]:
        stmt = select(Driver).options(selectinload(Driver.vehicle)).where(Driver.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_license(self, license_number: str) -> Optional[Driver]:
        stmt = select(Driver).options(selectinload(Driver.vehicle)).where(Driver.license_number == license_number)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> List[Driver]:
        stmt = select(Driver).options(selectinload(Driver.vehicle)).order_by(Driver.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_driver_with_vehicle(
        self,
        user_id: int,
        license_number: str,
        license_expiry,
        passport_number: str,
        registered_by: int,
        vehicle_data: VehicleCreate,
        license_photo_url: Optional[str] = None,
        passport_photo_url: Optional[str] = None,
        driver_photo_url: Optional[str] = None,
        license_photo_media_id: Optional[int] = None,
        passport_photo_media_id: Optional[int] = None,
        driver_photo_media_id: Optional[int] = None,
    ) -> Driver:
        driver = Driver(
            user_id=user_id,
            license_number=license_number,
            license_expiry=license_expiry,
            passport_number=passport_number,
            license_photo_url=license_photo_url,
            passport_photo_url=passport_photo_url,
            driver_photo_url=driver_photo_url,
            license_photo_media_id=license_photo_media_id,
            passport_photo_media_id=passport_photo_media_id,
            driver_photo_media_id=driver_photo_media_id,
            registered_by=registered_by,
            status=DriverStatus.PENDING,
            is_verified=False
        )
        self.db.add(driver)
        await self.db.flush()

        vehicle = Vehicle(
            driver_id=driver.id,
            brand=vehicle_data.brand,
            model=vehicle_data.model,
            year=vehicle_data.year,
            color=vehicle_data.color,
            license_plate=vehicle_data.license_plate,
            vin=vehicle_data.vin,
            seats=vehicle_data.seats,
            vehicle_type=vehicle_data.vehicle_type,
            vehicle_photo_url=vehicle_data.vehicle_photo_url,
            vehicle_photo_media_id=getattr(vehicle_data, "vehicle_photo_media_id", None),
        )
        self.db.add(vehicle)
        
        await self.db.commit()
        await self.db.refresh(driver)
        await self.db.refresh(vehicle)
        driver.vehicle = vehicle  # избегаем lazy load в async при доступе driver.vehicle
        logger.info(f"Driver created: {driver.id} for user {user_id}")
        return driver

    async def update_vehicle(self, driver_id: int, **fields) -> Optional[Vehicle]:
        stmt = select(Vehicle).where(Vehicle.driver_id == driver_id)
        result = await self.db.execute(stmt)
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            return None

        for key, value in fields.items():
            if value is not None and hasattr(vehicle, key):
                setattr(vehicle, key, value)
            if value is None and key in ["vehicle_photo_url", "vehicle_photo_media_id"] and hasattr(vehicle, key):
                setattr(vehicle, key, None)

        await self.db.commit()
        await self.db.refresh(vehicle)
        return vehicle

    async def update_driver_media(self, driver_id: int, **fields) -> Optional[Driver]:
        driver = await self.get_by_id(driver_id)
        if not driver:
            return None
        for key, value in fields.items():
            if hasattr(driver, key):
                setattr(driver, key, value)
        await self.db.commit()
        await self.db.refresh(driver)
        return driver

    async def update_status(self, driver_id: int, new_status: DriverStatus) -> Optional[Driver]:
        stmt = (
            update(Driver)
            .where(Driver.id == driver_id)
            .values(status=new_status)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return await self.get_by_id(driver_id)

    async def delete_driver(self, driver_id: int) -> bool:
        try:
            driver = await self.get_by_id(driver_id)
            if not driver:
                return False
            
            stmt = delete(Driver).where(Driver.id == driver_id)
            result = await self.db.execute(stmt)
            await self.db.commit()
            
            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"Driver deleted: {driver_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting driver {driver_id}: {e}")
            await self.db.rollback()
            return False

    async def get_all_vehicles(self) -> List[Vehicle]:
        stmt = select(Vehicle).order_by(Vehicle.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_vehicle_by_id(self, vehicle_id: int) -> Optional[Vehicle]:
        stmt = select(Vehicle).where(Vehicle.id == vehicle_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_vehicle_by_license_plate(self, license_plate: str) -> Optional[Vehicle]:
        stmt = select(Vehicle).where(Vehicle.license_plate == license_plate)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_vehicle_by_vin(self, vin: Optional[str]) -> Optional[Vehicle]:
        if not vin or not vin.strip():
            return None
        stmt = select(Vehicle).where(Vehicle.vin == vin.strip())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_vehicle(self, vehicle_id: int) -> bool:
        try:
            vehicle = await self.get_vehicle_by_id(vehicle_id)
            if not vehicle:
                return False
            
            stmt = delete(Vehicle).where(Vehicle.id == vehicle_id)
            result = await self.db.execute(stmt)
            await self.db.commit()
            
            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"Vehicle deleted: {vehicle_id}")
            return deleted
        except Exception as e:
            logger.error(f"Error deleting vehicle {vehicle_id}: {e}")
            await self.db.rollback()
            return False

