"""
Auth: login MVP (usuario/contraseña en variables de entorno).
Última mod: 2026-04-17 | JWT HS256 vía security.create_access_token.
"""
import secrets

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.security import create_access_token

router = APIRouter()
settings = get_settings()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _valid_credentials(username: str, password: str) -> bool:
    if username != settings.AUTH_USERNAME:
        return False
    return secrets.compare_digest(
        password.encode("utf-8"),
        settings.AUTH_PASSWORD.encode("utf-8"),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    if not _valid_credentials(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )
    token = await create_access_token({"sub": body.username})
    return TokenResponse(access_token=token)
