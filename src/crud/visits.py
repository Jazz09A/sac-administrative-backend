"""
CRUD for Visit model (ingreso/salida contribuyentes).
Última mod: 2026-04-17 | Changes: Init core ops + filters. 
"""
from typing import List, Optional
from datetime import date
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_
from sqlmodel import select
from src.models.contributor import Contributor
from src.models.visit import Visit, VisitCreate, VisitUpdateExit, VisitStatus

async def create_visit(
    session: AsyncSession, visit_in: VisitCreate
) -> Visit:
    """Registro ingreso: valida contributor existe."""
    from .contributors import get_or_create_contributor_for_visit  # Lazy import

    contributor = await get_or_create_contributor_for_visit(
        session, visit_in.contributor_rif, visit_in.contributor_name
    )

    db_visit = Visit(
        contributor_id=contributor.id,
        fiscal_id=visit_in.fiscal_id,
        reason=visit_in.reason,
        observations=visit_in.observations,
        received_by=visit_in.responsible_person,
        department=visit_in.department,
        file_number=visit_in.file_number,
        entry_date=visit_in.entry_date,
        entry_time=visit_in.entry_time,
        signature_image_url=visit_in.signature_image_url,
    )
    db_visit.status = VisitStatus.ESPERA
    session.add(db_visit)
    await session.commit()
    await session.refresh(db_visit)
    return db_visit

async def get_visit(session: AsyncSession, visit_id: UUID) -> Optional[Visit]:
    """Get by ID."""
    statement = select(Visit).where(Visit.id == visit_id, Visit.deleted_at.is_(None))
    result = await session.execute(statement)
    return result.scalar_one_or_none()

async def get_visits(
    session: AsyncSession,
    contributor_id: Optional[int] = None,
    rif: Optional[str] = None,
    status: Optional[str] = None,
    entry_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Visit]:
    """Filtros MVP: rif/status/fecha."""
    statement = select(Visit).where(Visit.deleted_at.is_(None))
    if contributor_id:
        statement = statement.where(Visit.contributor_id == contributor_id)
    if rif:
        statement = statement.join(Contributor).where(Contributor.rif == rif)
    if status:
        statement = statement.where(Visit.status == status)
    if entry_date:
        statement = statement.where(Visit.entry_date == entry_date)
    statement = statement.offset(skip).limit(limit)
    
    result = await session.execute(statement)
    return list(result.scalars().all())

async def update_visit_exit(
    session: AsyncSession, visit_id: UUID, exit_data: VisitUpdateExit
) -> Optional[Visit]:
    """PATCH salida: valida existe y status=espera."""
    visit = await get_visit(session, visit_id)
    if not visit or visit.status != VisitStatus.ESPERA:
        return None
    visit.exit_date = exit_data.exit_date
    visit.exit_time = exit_data.exit_time
    visit.status = exit_data.status or VisitStatus.FINALIZADO
    session.add(visit)
    await session.commit()
    await session.refresh(visit)
    return visit

async def get_open_visits(session: AsyncSession) -> List[Visit]:
    """Dashboard: en espera."""
    statement = select(Visit).where(Visit.status == VisitStatus.ESPERA, Visit.deleted_at.is_(None))
    result = await session.execute(statement)
    return list(result.scalars().all())