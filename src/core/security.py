"""
JWT utilities (MVP: básico, activar con REQUIRE_AUTH).
Última mod: 2026-04-17 09:01 | Changes: create_token, verify (funcionario).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from .config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

class TokenData(BaseModel):
    username: Optional[str] = None

class FuncionarioBase(BaseModel):
    username: str
    # Future: role

async def create_access_token(data: dict) -> str:
    """JWT para funcionario."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

async def verify_token(token: str) -> Optional[FuncionarioBase]:
    """Verifica JWT (MVP: simple)."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            return None
        return FuncionarioBase(username=username)
    except JWTError:
        return None

# Future deps
async def get_current_user(token: str = Depends(oauth2_scheme)) -> FuncionarioBase:
    user = await verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user