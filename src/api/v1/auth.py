"""
Auth: login MVP (usuario/contraseña en variables de entorno).
Última mod: 2026-04-17 | JWT HS256 vía security.create_access_token.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.database import get_db
from src.core.security import create_access_token, create_refresh_token, verify_password
from src.crud.users import get_user_by_person_id, update_last_login, update_refresh_token

router = APIRouter()
settings = get_settings()


class LoginRequest(BaseModel):
    person_id: str = Field(..., min_length=1, max_length=20)
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await get_user_by_person_id(db, body.person_id)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo",
        )

    access_token = await create_access_token({"sub": user.person_id})
    refresh_token = create_refresh_token()
    refresh_token_expires_at = datetime.utcnow() + timedelta(days=7)

    await update_last_login(db, user)
    await update_refresh_token(db, user, refresh_token, refresh_token_expires_at)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
