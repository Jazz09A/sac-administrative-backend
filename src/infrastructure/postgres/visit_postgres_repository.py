from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from src.domain.repositories.visit_repository import VisitRepository
from src.models.contributor import Contributor
from src.models.fiscal import Fiscal
from src.models.visit import Visit, VisitStatus, format_ticket_no


class PostgresVisitRepository(VisitRepository):
    @staticmethod
    def _with_relations(statement):
        return statement.options(
            selectinload(Visit.fiscal),
            selectinload(Visit.contributor),
        )

    def _history_base_statement(
        self,
        *,
        rif: str | None = None,
        contributor_name: str | None = None,
        file_number: str | None = None,
        department: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        status_list: list[VisitStatus] | None = None,
    ):
        statement = (
            select(
                Visit.id,
                Contributor.rif,
                Contributor.name,
                Visit.file_number,
                Visit.department,
                Visit.reason,
                Visit.status,
                Fiscal.name,
            )
            .join(Contributor, Visit.contributor_id == Contributor.id)
            .outerjoin(Fiscal, Visit.fiscal_id == Fiscal.id)
            .where(Visit.deleted_at.is_(None))
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
        return statement

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, visit_data: dict, responsible_snapshot: str) -> Visit:
        async with self.session.begin_nested():
            db_visit = Visit(**visit_data)
            db_visit.status = VisitStatus.ESPERA
            db_visit.received_by = responsible_snapshot
            self.session.add(db_visit)
            await self.session.flush()
            await self.session.refresh(db_visit)
        created = await self.get(db_visit.id)
        if created is None:
            raise RuntimeError("No se pudo recargar la visita creada")
        return created

    async def get(self, visit_id: UUID) -> Visit | None:
        statement = self._with_relations(
            select(Visit).where(Visit.id == visit_id, Visit.deleted_at.is_(None))
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        contributor_id: int | None = None,
        rif: str | None = None,
        status: str | None = None,
        fiscal_id: int | None = None,
        entry_date: date | None = None,
        open_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Visit]:
        statement = self._with_relations(select(Visit)).where(Visit.deleted_at.is_(None))
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
        if open_only:
            statement = statement.where(
                Visit.exit_at.is_(None),
                Visit.status != VisitStatus.FINALIZADO,
            )
        statement = statement.order_by(Visit.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update(self, visit_id: UUID, visit_data: dict[str, Any]) -> Visit | None:
        visit = await self.get(visit_id)
        if not visit:
            return None

        for field_name, value in visit_data.items():
            setattr(visit, field_name, value)
        visit.updated_at = datetime.utcnow()

        self.session.add(visit)
        await self.session.flush()
        return await self.get(visit_id)

    async def mark_as_attended(self, visit_id: UUID) -> Visit | None:
        visit = await self.get(visit_id)
        if not visit or visit.status != VisitStatus.ESPERA:
            return None

        visit.status = VisitStatus.ATENDIDO
        self.session.add(visit)
        await self.session.flush()
        return await self.get(visit.id)

    async def soft_delete(self, visit_id: UUID) -> Visit | None:
        visit = await self.get(visit_id)
        if not visit:
            return None

        visit.deleted_at = datetime.utcnow()
        visit.updated_at = datetime.utcnow()
        self.session.add(visit)
        await self.session.flush()
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
        status_list: list[VisitStatus] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        statement = self._history_base_statement(
            rif=rif,
            contributor_name=contributor_name,
            file_number=file_number,
            department=department,
            date_from=date_from,
            date_to=date_to,
            status_list=status_list,
        ).order_by(Visit.created_at.desc())
        statement = statement.offset(skip).limit(limit)
        result = await self.session.execute(statement)
        rows = result.all()
        return [
            {
                "id": row[0],
                "rif": row[1],
                "contribuyente": row[2],
                "registro": row[3],
                "depto": row[4],
                "motivo": row[5],
                "estado": row[6],
                "fiscal": row[7],
            }
            for row in rows
        ]

    async def count_history(
        self,
        *,
        rif: str | None = None,
        contributor_name: str | None = None,
        file_number: str | None = None,
        department: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        status_list: list[VisitStatus] | None = None,
    ) -> int:
        base = self._history_base_statement(
            rif=rif,
            contributor_name=contributor_name,
            file_number=file_number,
            department=department,
            date_from=date_from,
            date_to=date_to,
            status_list=status_list,
        ).subquery()
        result = await self.session.execute(select(func.count()).select_from(base))
        return int(result.scalar_one())

    async def allocate_next_ticket(self, entry_date: date) -> str:
        lock_key = int(entry_date.strftime("%Y%m%d"))
        await self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
        prefix = f"T-{entry_date.strftime('%Y%m%d')}-"
        statement = select(Visit.ticket_no).where(Visit.ticket_no.startswith(prefix))
        result = await self.session.execute(statement)
        max_seq = 0
        for (ticket_no,) in result.all():
            if not ticket_no:
                continue
            suffix = ticket_no[len(prefix) :]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
        return format_ticket_no(entry_date, max_seq + 1)

    async def list_queue(self, *, department: str | None = None) -> list[Visit]:
        statement = self._with_relations(select(Visit)).where(
            Visit.deleted_at.is_(None),
            Visit.status.in_([VisitStatus.ESPERA, VisitStatus.EN_ATENCION]),
        )
        if department is not None:
            statement = statement.where(Visit.department == department)
        statement = statement.order_by(Visit.created_at.asc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_by_entry_date(self, target_date: date) -> list[Visit]:
        statement = self._with_relations(select(Visit)).where(
            Visit.deleted_at.is_(None),
            Visit.entry_date == target_date,
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
