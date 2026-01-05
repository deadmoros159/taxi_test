from sqlalchemy.orm import Session
from typing import Optional
from app.models.token import RefreshToken
from datetime import datetime


class TokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_refresh_token(self, token_id: str) -> Optional[RefreshToken]:
        return self.db.query(RefreshToken).filter(RefreshToken.token == token_id).first()

    def create_refresh_token(self, user_id: int, token: str, expires_at: datetime) -> RefreshToken:
        db_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
        self.db.add(db_token)
        self.db.commit()
        self.db.refresh(db_token)
        return db_token

    def deactivate_token(self, token_id: str) -> bool:
        token = self.get_refresh_token(token_id)
        if token:
            token.is_active = False
            self.db.commit()
            return True
        return False