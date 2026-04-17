"""
User model para administradores del sistema.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    person_id: str = PydanticField(
        ...,
        min_length=5,
        max_length=20,
        description="Cedula del usuario administrador",
    )
    full_name: str = PydanticField(..., min_length=1, max_length=255)
    email: Optional[str] = PydanticField(default=None, max_length=255)
    is_active: bool = Field(default=True)


class UserCreate(UserBase):
    password: str = PydanticField(..., min_length=8, max_length=256)


class UserUpdate(SQLModel):
    full_name: Optional[str] = PydanticField(default=None, min_length=1, max_length=255)
    email: Optional[str] = PydanticField(default=None, max_length=255)
    password: Optional[str] = PydanticField(default=None, min_length=8, max_length=256)
    is_active: Optional[bool] = None


class UserPublic(UserBase):
    id: Optional[UUID] = Field(default=None)
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserLogin(SQLModel):
    person_id: str = PydanticField(..., min_length=1, max_length=20)
    password: str = PydanticField(..., min_length=1, max_length=256)


class User(UserBase, table=True):  # type: ignore
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    person_id: str = Field(index=True, unique=True, max_length=20)
    email: Optional[str] = Field(default=None, index=True, unique=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    last_login_at: Optional[datetime] = Field(default=None)
    refresh_token: Optional[str] = Field(default=None, max_length=512)
    refresh_token_expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
