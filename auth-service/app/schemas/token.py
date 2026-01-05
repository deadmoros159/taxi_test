from pydantic import BaseModel

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenData(BaseModel):
    user_id: int
    phone_number: str