from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, List
from app.models.driver import Driver, Vehicle, DriverStatus
from app.schemas.driver import VehicleCreate
import logging

logger = logging.getLogger(__name__)


class DriverRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, driver_id: int) -> Optional[Driver]:
        """Получить водителя по ID"""
        stmt = select(Driver).where(Driver.id == driver_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> Optional[Driver]:
        """Получить водителя по user_id"""
        stmt = select(Driver).where(Driver.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_license(self, license_number: str) -> Optional[Driver]:
        """Получить водителя по номеру водительского удостоверения"""
        stmt = select(Driver).where(Driver.license_number == license_number)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> List[Driver]:
        """Получить всех водителей"""
        stmt = select(Driver).order_by(Driver.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_driver_with_vehicle(
        self,
        user_id: int,
        license_number: str,
        license_expiry,
        passport_number: str,
        registered_by: int,
        vehicle_data: VehicleCreate
    ) -> Driver:
        """Создать водителя с автомобилем"""
        # Создаем водителя
        driver = Driver(
            user_id=user_id,
            license_number=license_number,
            license_expiry=license_expiry,
            passport_number=passport_number,
            registered_by=registered_by,
            status=DriverStatus.PENDING,
            is_verified=False
        )
        self.db.add(driver)
        await self.db.flush()  # Получаем ID водителя
        
        # Создаем автомобиль
        vehicle = Vehicle(
            driver_id=driver.id,
            brand=vehicle_data.brand,
            model=vehicle_data.model,
            year=vehicle_data.year,
            color=vehicle_data.color,
            license_plate=vehicle_data.license_plate,
            vin=vehicle_data.vin,
            seats=vehicle_data.seats,
            vehicle_type=vehicle_data.vehicle_type
        )
        self.db.add(vehicle)
        
        await self.db.commit()
        await self.db.refresh(driver)
        await self.db.refresh(vehicle)
        
        logger.info(f"Driver created: {driver.id} for user {user_id}")
        return driver

    async def update_status(self, driver_id: int, new_status: DriverStatus) -> Optional[Driver]:
        """Обновить статус водителя"""
        stmt = (
            update(Driver)
            .where(Driver.id == driver_id)
            .values(status=new_status)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return await self.get_by_id(driver_id)

    async def verify_driver(self, driver_id: int) -> Optional[Driver]:
        """Верифицировать водителя (диспетчер проверил документы)"""
        stmt = (
            update(Driver)
            .where(Driver.id == driver_id)
            .values(is_verified=True, status=DriverStatus.ACTIVE)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return await self.get_by_id(driver_id)

