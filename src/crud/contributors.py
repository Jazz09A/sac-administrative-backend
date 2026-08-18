"""
CRUD operations for Contributor model.
Última mod: 2026-04-17 | Changes: Init get/create. Tests pending.
"""
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from src.models.contributor import Contributor, ContributorCreate, ContributorType, ContributorUpdate, ContributorPublic

async def get_contributor_by_cedula(
    session: AsyncSession, cedula: str
) -> Optional[Contributor]:
    normalized = cedula.strip()
    if not normalized:
        return None
    result = await session.execute(
        select(Contributor).where(Contributor.cedula == normalized)
    )
    return result.scalar_one_or_none()


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
    """Create new or get existing by cédula, then RIF (get_or_create)."""
    if contributor_in.cedula:
        contributor = await get_contributor_by_cedula(session, contributor_in.cedula)
        if contributor:
            return contributor
    if contributor_in.rif:
        contributor = await get_contributor_by_rif(session, contributor_in.rif)
        if contributor:
            return contributor
    db_contributor = Contributor.model_validate(contributor_in)
    session.add(db_contributor)
    await session.commit()
    await session.refresh(db_contributor)
    return db_contributor


async def get_or_create_contributor_by_cedula(
    session: AsyncSession,
    cedula: str,
    *,
    name: str | None = None,
    rif: str | None = None,
) -> Contributor:
    """Resolve contributor by cédula; create minimal row without requiring RIF or name."""
    normalized = cedula.strip()
    if not normalized:
        raise ValueError("Cédula es obligatoria")
    if rif and rif.strip().upper().startswith("TEMP-"):
        raise ValueError("RIF temporal no permitido")
    existing = await get_contributor_by_cedula(session, normalized)
    if existing:
        return existing
    normalized_rif = rif.strip() if rif else None
    if normalized_rif:
        by_rif = await get_contributor_by_rif(session, normalized_rif)
        if by_rif is not None:
            if by_rif.cedula and by_rif.cedula != normalized:
                raise ValueError("El RIF ya está registrado en otro contribuyente")
            if not by_rif.cedula:
                by_rif.cedula = normalized
                session.add(by_rif)
                await session.commit()
                await session.refresh(by_rif)
            return by_rif
    db_contributor = Contributor(
        cedula=normalized,
        rif=normalized_rif or None,
        name=name.strip() if name else None,
        type=ContributorType.NATURAL,
    )
    session.add(db_contributor)
    await session.commit()
    await session.refresh(db_contributor)
    return db_contributor


async def get_or_create_contributor_for_visit(
    session: AsyncSession, rif: str, name: str
) -> Contributor:
    """Resolve contributor by real RIF; create minimal row if missing (visit flow)."""
    normalized = rif.strip()
    if normalized.upper().startswith("TEMP-"):
        raise ValueError("RIF temporal no permitido en registro de visita")
    existing = await get_contributor_by_rif(session, normalized)
    if existing:
        return existing
    db_contributor = Contributor(
        rif=normalized,
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