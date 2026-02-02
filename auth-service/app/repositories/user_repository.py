from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, update, func
from typing import Optional, List
from app.models.user import User
from app.models.role import UserRole
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_phone(self, phone_number: str) -> Optional[User]:
        """Получить пользователя по номеру телефона"""
        from sqlalchemy.future import select
        stmt = select(User).where(User.phone_number == phone_number)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Получить пользователя по email"""
        from sqlalchemy.future import select
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        from sqlalchemy.future import select
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> Optional[User]:
        """Получить пользователя по Telegram user ID"""
        from sqlalchemy.future import select
        stmt = select(User).where(User.telegram_user_id == telegram_user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, phone_number: str = None, email: str = None, full_name: str = None, **kwargs) -> User:
        """Создать нового пользователя с именем"""
        user_data = {
            "full_name": full_name or "User",  # Обязательный параметр
            **kwargs
        }
        if phone_number:
            user_data["phone_number"] = phone_number
        if email:
            user_data["email"] = email
        
        user = User(**user_data)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        identifier = phone_number or email or f"ID:{user.id}"
        logger.info(f"User created: {user.id} - {identifier}")
        return user

    async def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Обновить данные пользователя"""
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(**kwargs, updated_at=func.now())
            .execution_options(synchronize_session="fetch")
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return await self.get_by_id(user_id)

    async def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя из БД"""
        try:
            # Сначала удаляем связанные refresh токены
            from app.models.token import RefreshToken
            delete_tokens = delete(RefreshToken).where(RefreshToken.user_id == user_id)
            await self.db.execute(delete_tokens)

            # Затем удаляем пользователя
            stmt = delete(User).where(User.id == user_id)
            result = await self.db.execute(stmt)
            await self.db.commit()

            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"User deleted: {user_id}")
            return deleted

        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            await self.db.rollback()
            return False

    async def delete_user_by_phone(self, phone_number: str) -> bool:
        """Удалить пользователя по номеру телефона"""
        user = await self.get_by_phone(phone_number)
        if user:
            return await self.delete_user(user.id)
        return False

    async def deactivate_user(self, user_id: int) -> bool:
        """Деактивировать пользователя (мягкое удаление)"""
        user = await self.update_user(user_id, is_active=False)
        return user is not None

    async def activate_user(self, user_id: int) -> bool:
        """Активировать пользователя"""
        user = await self.update_user(user_id, is_active=True, is_verified=True)
        return user is not None

    async def update_firebase_uid(self, user_id: int, firebase_uid: str) -> bool:
        """Обновить Firebase UID"""
        user = await self.update_user(user_id, firebase_uid=firebase_uid)
        return user is not None

    async def get_all_users(self, role: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[User]:
        """Получить всех пользователей с фильтрацией по роли"""
        from sqlalchemy.future import select
        stmt = select(User)
        if role:
            stmt = stmt.where(User.role == role)
        stmt = stmt.order_by(User.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_users_by_role(self, role: str, limit: int = 100, offset: int = 0) -> List[User]:
        """Получить пользователей по роли"""
        return await self.get_all_users(role=role, limit=limit, offset=offset)