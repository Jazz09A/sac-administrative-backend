"""
CRUD operations para usuarios administradores.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.security import hash_password
from src.models.user import User, UserCreate, UserUpdate


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    return await session.get(User, user_id)


async def get_user_by_person_id(session: AsyncSession, person_id: str) -> Optional[User]:
    result = await session.execute(
        select(User).where(User.person_id == person_id.strip())
    )
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == email.strip().lower()))
    return result.scalar_one_or_none()


async def get_users(session: AsyncSession, skip: int = 0, limit: int = 100) -> List[User]:
    result = await session.execute(select(User).offset(skip).limit(limit))
    return list(result.scalars().all())


async def create_user(session: AsyncSession, user_in: UserCreate) -> User:
    db_user = User(
        person_id=user_in.person_id.strip(),
        full_name=user_in.full_name.strip(),
        email=user_in.email.strip().lower() if user_in.email else None,
        is_active=user_in.is_active,
        hashed_password=hash_password(user_in.password),
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user


async def update_user(
    session: AsyncSession,
    user_id: UUID,
    user_in: UserUpdate,
) -> Optional[User]:
    user = await get_user_by_id(session, user_id)
    if not user:
        return None

    payload = user_in.model_dump(exclude_unset=True)
    if "password" in payload and payload["password"]:
        user.hashed_password = hash_password(payload.pop("password"))

    if "email" in payload and payload["email"] is not None:
        payload["email"] = payload["email"].strip().lower()
    if "full_name" in payload and payload["full_name"] is not None:
        payload["full_name"] = payload["full_name"].strip()

    for field, value in payload.items():
        setattr(user, field, value)

    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user_id: UUID) -> bool:
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    await session.delete(user)
    await session.commit()
    return True


async def update_last_login(session: AsyncSession, user: User) -> User:
    user.last_login_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_refresh_token(
    session: AsyncSession,
    user: User,
    refresh_token: Optional[str],
    expires_at: Optional[datetime],
) -> User:
    user.refresh_token = refresh_token
    user.refresh_token_expires_at = expires_at
    user.updated_at = datetime.utcnow()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
