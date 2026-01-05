from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.role import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    role = Column(String, default=UserRole.PASSENGER.value, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def has_role(self, role: UserRole) -> bool:
        """Проверка, имеет ли пользователь указанную роль"""
        return self.role == role.value
    
    def is_admin(self) -> bool:
        """Проверка, является ли пользователь админом"""
        return self.role == UserRole.ADMIN.value
    
    def is_dispatcher(self) -> bool:
        """Проверка, является ли пользователь диспетчером"""
        return self.role == UserRole.DISPATCHER.value
    
    def is_driver(self) -> bool:
        """Проверка, является ли пользователь водителем"""
        return self.role == UserRole.DRIVER.value
    
    def is_passenger(self) -> bool:
        """Проверка, является ли пользователь пассажиром"""
        return self.role == UserRole.PASSENGER.value