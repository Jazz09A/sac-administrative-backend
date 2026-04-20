from datetime import date
from typing import Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.domain.repositories.visit_repository import VisitRepository
from src.models.contributor import Contributor
from src.models.visit import Visit, VisitStatus, VisitUpdateExit


class PostgresVisitRepository(VisitRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, visit_data: dict, responsible_snapshot: str) -> Visit:
        db_visit = Visit(**visit_data)
        db_visit.status = VisitStatus.ESPERA
        db_visit.received_by = responsible_snapshot
        self.session.add(db_visit)
        await self.session.flush()
        await self.session.refresh(db_visit)
        return db_visit

    async def get(self, visit_id: UUID) -> Visit | None:
        result = await self.session.execute(select(Visit).where(Visit.id == visit_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        contributor_id: int | None = None,
        rif: str | None = None,
        status: str | None = None,
        fiscal_id: int | None = None,
        entry_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Visit]:
        statement = select(Visit)
        if contributor_id:
            statement = statement.where(Visit.contributor_id == contributor_id)
        if fiscal_id:
            statement = statement.where(Visit.fiscal_id == fiscal_id)
        if rif:
            statement = statement.join(Contributor).where(Contributor.rif.ilike(f"%{rif}%"))
        if status:
            statement = statement.where(Visit.status == status)
        if entry_date:
            statement = statement.where(Visit.entry_date == entry_date)
        statement = statement.order_by(Visit.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def register_exit(self, visit_id: UUID, exit_data: VisitUpdateExit) -> Visit | None:
        visit = await self.get(visit_id)
        if not visit or visit.status != VisitStatus.ESPERA:
            return None

        visit.exit_date = exit_data.exit_date
        visit.exit_time = exit_data.exit_time
        visit.status = exit_data.status or VisitStatus.FINALIZADO
        self.session.add(visit)
        await self.session.flush()
        await self.session.refresh(visit)
        return visit

    async def list_history(
        self,
        *,
        rif: str | None = None,
        contributor_name: str | None = None,
        file_number: str | None = None,
        department: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        status_list: List[VisitStatus] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[dict[str, Any]]:
        statement = (
            select(
                Contributor.rif,
                Contributor.name,
                Visit.file_number,
                Visit.department,
                Visit.reason,
                Visit.status,
            )
            .join(Contributor, Visit.contributor_id == Contributor.id)
            .order_by(Visit.created_at.desc())
        )
        if rif:
            statement = statement.where(Contributor.rif.ilike(f"%{rif}%"))
        if contributor_name:
            statement = statement.where(Contributor.name.ilike(f"%{contributor_name}%"))
        if file_number:
            statement = statement.where(Visit.file_number.ilike(f"%{file_number}%"))
        if department:
            statement = statement.where(Visit.department.ilike(f"%{department}%"))
        if date_from:
            statement = statement.where(Visit.entry_date >= date_from)
        if date_to:
            statement = statement.where(Visit.entry_date <= date_to)
        if status_list:
            statement = statement.where(Visit.status.in_(status_list))

        statement = statement.offset(skip).limit(limit)
        result = await self.session.execute(statement)
        rows = result.all()
        return [ 
            {
                "rif": row[0],
                "contribuyente": row[1],
                "registro": row[2],
                "depto": row[3],
                "motivo": row[4],
                "estado": row[5],
            }
            for row in rows
        ]
