"""
JWT utilities (MVP: básico, activar con REQUIRE_AUTH).
Última mod: 2026-04-17 09:01 | Changes: create_token, verify (funcionario).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import secrets

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from .config import get_settings

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

class TokenData(BaseModel):
    person_id: Optional[str] = None
    role: Optional[str] = None

class CurrentUser(BaseModel):
    person_id: str
    role: str

async def create_access_token(data: dict) -> str:
    """JWT para funcionario."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def create_refresh_token(length: int = 64) -> str:
    """Genera refresh token aleatorio URL-safe."""
    return secrets.token_urlsafe(length)


def _normalize_password_for_bcrypt(password: str) -> bytes:
    """
    Bcrypt only accepts up to 72 bytes.
    For longer passwords, pre-hash with SHA-256 (hex) to keep deterministic verification.
    """
    raw = password.encode("utf-8")
    if len(raw) <= 72:
        return raw
    return hashlib.sha256(raw).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    """Genera hash bcrypt para contrasena."""
    normalized = _normalize_password_for_bcrypt(password)
    hashed = bcrypt.hashpw(normalized, bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Valida contrasena en texto plano contra hash bcrypt."""
    normalized = _normalize_password_for_bcrypt(plain_password)
    return bcrypt.checkpw(normalized, hashed_password.encode("utf-8"))

async def verify_token(token: str) -> Optional[CurrentUser]:
    """Verifica JWT y retorna datos del usuario."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        person_id: str = payload.get("sub")
        role: str = payload.get("role", "user")
        if person_id is None:
            return None
        return CurrentUser(person_id=person_id, role=role)
    except JWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    """Dependencia para obtener el usuario actual desde el token JWT."""
    user = await verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


async def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Dependencia que requiere que el usuario sea administrador."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de administrador"
        )
    return current_user