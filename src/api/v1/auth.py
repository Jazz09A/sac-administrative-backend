"""
Auth: login MVP (usuario/contraseña en variables de entorno).
Última mod: 2026-04-21 | JWT HS256 vía security.create_access_token. Agregado endpoint /me.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.database import get_db
from src.core.security import (
    CurrentUser,
    create_access_token,
    create_refresh_token,
    get_current_user,
    verify_password,
)
from src.crud.users import get_user_by_email, get_user_by_person_id, update_last_login, update_refresh_token

router = APIRouter()
settings = get_settings()


class LoginRequest(BaseModel):
    person_id: str = Field(..., min_length=1, max_length=20)
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


class MeResponse(BaseModel):
    id: str
    fullName: str
    full_name: str
    role: str
    username: str
    person_id: str


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    person_id = body.person_id.strip().upper()
    user = await get_user_by_person_id(db, person_id)
    if user is None and person_id.isdigit():
        user = await get_user_by_person_id(db, f"V{person_id}")
    if user is None and "@" in body.person_id:
        user = await get_user_by_email(db, body.person_id)
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

    access_token = await create_access_token({"sub": user.person_id, "role": user.role})
    refresh_token = create_refresh_token()
    refresh_token_expires_at = datetime.utcnow() + timedelta(days=7)

    await update_last_login(db, user)
    await update_refresh_token(db, user, refresh_token, refresh_token_expires_at)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user.role,
        full_name=user.full_name,
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Obtiene los datos del usuario autenticado."""
    user = await get_user_by_person_id(db, current_user.person_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return MeResponse(
        id=str(user.id),
        fullName=user.full_name,
        full_name=user.full_name,
        role=user.role,
        username=user.person_id,
        person_id=user.person_id,
    )
