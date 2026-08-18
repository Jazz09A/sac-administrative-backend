"""
API Users: CRUD de administradores.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import require_admin
from src.crud.users import (
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_person_id,
    get_users,
    update_user,
)
from src.models.user import UserCreate, UserPublic, UserUpdate

router = APIRouter()


@router.post("/", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> UserPublic:
    existing_by_person_id = await get_user_by_person_id(db, user_in.person_id)
    if existing_by_person_id:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con esa cedula")

    if user_in.email:
        existing_by_email = await get_user_by_email(db, user_in.email)
        if existing_by_email:
            raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    user = await create_user(db, user_in)
    return user


@router.get("/", response_model=List[UserPublic])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> List[UserPublic]:
    users = await get_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserPublic)
async def read_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> UserPublic:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@router.put("/{user_id}", response_model=UserPublic)
async def update_existing_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> UserPublic:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user_in.email:
        existing_by_email = await get_user_by_email(db, user_in.email)
        if existing_by_email and existing_by_email.id != user.id:
            raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    updated = await update_user(db, user_id, user_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return updated


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_existing_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> None:
    deleted = await delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
