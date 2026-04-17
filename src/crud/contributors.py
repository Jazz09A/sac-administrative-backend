"""
CRUD operations for Contributor model.
Última mod: 2026-04-17 | Changes: Init get/create. Tests pending.
"""
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from src.models.contributor import Contributor, ContributorCreate, ContributorType, ContributorUpdate, ContributorPublic

async def get_contributor_by_rif(
    session: AsyncSession, rif: str
) -> Optional[Contributor]:
    """Get contributor by RIF (unique)."""
    result = await session.execute(select(Contributor).where(Contributor.rif == rif))
    return result.scalar_one_or_none()

async def get_contributor(session: AsyncSession, contributor_id: int) -> Optional[Contributor]:
    """Get by ID."""
    result = await session.get(Contributor, contributor_id)
    return result


async def get_contributor_by_name(session: AsyncSession, name: str) -> Optional[Contributor]:
    """Case-insensitive lookup by contributor name."""
    result = await session.execute(
        select(Contributor).where(func.lower(Contributor.name) == name.strip().lower())
    )
    return result.scalar_one_or_none()

async def get_contributors(
    session: AsyncSession, skip: int = 0, limit: int = 100
) -> List[Contributor]:
    """List all contributors."""
    result = await session.execute(select(Contributor).offset(skip).limit(limit))
    return list(result.scalars().all())

async def create_contributor(
    session: AsyncSession, contributor_in: ContributorCreate
) -> Contributor:
    """Create new or get existing by RIF (get_or_create pattern)."""
    contributor = await get_contributor_by_rif(session, contributor_in.rif)
    if contributor:
        return contributor  # Idempotent
    db_contributor = Contributor.model_validate(contributor_in)
    session.add(db_contributor)
    await session.commit()
    await session.refresh(db_contributor)
    return db_contributor


async def create_minimal_contributor(session: AsyncSession, name: str) -> Contributor:
    """Create a minimal contributor row for visit-driven flow."""
    db_contributor = Contributor(
        rif=f"TEMP-{uuid4().hex[:10].upper()}",
        name=name.strip(),
        type=ContributorType.NATURAL,
    )
    session.add(db_contributor)
    await session.commit()
    await session.refresh(db_contributor)
    return db_contributor

async def update_contributor(
    session: AsyncSession,
    contributor_id: int,
    contributor_in: ContributorUpdate
) -> Optional[Contributor]:
    """Partial update."""
    contributor = await get_contributor(session, contributor_id)
    if not contributor:
        return None
    contributor_in_dict = contributor_in.model_dump(exclude_unset=True)
    for field, value in contributor_in_dict.items():
        setattr(contributor, field, value)
    session.add(contributor)
    await session.commit()
    await session.refresh(contributor)
    return contributor

async def delete_contributor(
    session: AsyncSession, contributor_id: int
) -> bool:
    """Soft delete or hard? MVP: hard."""
    contributor = await get_contributor(session, contributor_id)
    if not contributor:
        return False
    await session.delete(contributor)
    await session.commit()
    return True