from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from app.models.token import RefreshToken
from datetime import datetime


class TokenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_refresh_token(self, token_id: str) -> Optional[RefreshToken]:
        stmt = select(RefreshToken).where(RefreshToken.token == token_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_refresh_token(self, user_id: int, token: str, expires_at: datetime) -> RefreshToken:
        db_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        self.db.add(db_token)
        await self.db.commit()
        await self.db.refresh(db_token)
        return db_token

    async def deactivate_token(self, token_id: str) -> bool:
        token = await self.get_refresh_token(token_id)
        if token:
            token.is_active = False
            await self.db.commit()
            return True
        return False