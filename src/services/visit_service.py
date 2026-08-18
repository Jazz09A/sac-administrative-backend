from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError

from src.domain.repositories.contributor_repository import ContributorRepository
from src.domain.repositories.fiscal_repository import FiscalRepository
from src.domain.repositories.visit_repository import VisitRepository
from src.models.visit import (
    CLOSE_STATUSES,
    EXIT_ALLOWED_STATUSES,
    VENEZUELA_TZ,
    Visit,
    VisitClose,
    VisitCreate,
    VisitDayMetrics,
    VisitIntake,
    VisitStatus,
    VisitUpdate,
    VisitUpdateExit,
    visit_duration_metrics,
)

_TICKET_ALLOCATE_ATTEMPTS = 3


class VisitFlowError(ValueError):
    """Transición de estado inválida en el flujo operativo de visita."""


class ContributorRifConflict(ValueError):
    """El RIF ya pertenece a otro contribuyente."""


def resolve_visit_list_entry_date(
    *,
    entry_date: date | None,
    open_only: bool,
    today: date,
) -> date | None:
    """Contrato: open=true no aplica default de hoy; entry_date explícito siempre gana."""
    if entry_date is not None:
        return entry_date
    if open_only:
        return None
    return today


def _is_ticket_no_conflict(exc: IntegrityError) -> bool:
    origin = exc.orig if exc.orig is not None else exc
    message = str(origin).lower()
    return "ticket_no" in message or "ix_visit_ticket_no" in message


def _average(values: list[int]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


class VisitService:
    def __init__(
        self,
        contributor_repo: ContributorRepository,
        fiscal_repo: FiscalRepository,
        visit_repo: VisitRepository,
    ):
        self.contributor_repo = contributor_repo
        self.fiscal_repo = fiscal_repo
        self.visit_repo = visit_repo

    async def create(self, visit_in: VisitCreate) -> Visit:
        last_error: IntegrityError | None = None
        for _attempt in range(_TICKET_ALLOCATE_ATTEMPTS):
            try:
                return await self._create_once(visit_in)
            except IntegrityError as exc:
                last_error = exc
                if not _is_ticket_no_conflict(exc):
                    raise
        assert last_error is not None
        raise last_error

    async def _create_once(self, visit_in: VisitCreate) -> Visit:
        contributor = await self.contributor_repo.get_or_create_by_cedula(
            visit_in.contributor_cedula,
            name=visit_in.contributor_name,
            rif=visit_in.contributor_rif,
        )

        fiscal_id = None
        if visit_in.fiscal_id:
            fiscal = await self._resolve_fiscal(visit_in.fiscal_id)
            if fiscal is None:
                raise ValueError("Fiscal no existe")
            if not fiscal.status:
                raise ValueError("Fiscal inactivo")
            fiscal_id = fiscal.id

        responsible_person = (visit_in.responsible_person or "").strip()
        entry_date = visit_in.entry_date
        entry_time = visit_in.entry_time
        if entry_date is None or entry_time is None:
            now_local = datetime.now(VENEZUELA_TZ)
            entry_date = entry_date or now_local.date()
            entry_time = entry_time or now_local.time().replace(tzinfo=None, microsecond=0)
        ticket_no = await self.visit_repo.allocate_next_ticket(entry_date)
        visit_data = {
            "contributor_id": contributor.id,
            "fiscal_id": fiscal_id,
            "reason": visit_in.reason,
            "observations": visit_in.observations,
            "received_by": responsible_person or None,
            "department": visit_in.department,
            "file_number": visit_in.file_number,
            "entry_date": entry_date,
            "entry_time": entry_time,
            "signature_image_url": visit_in.signature_image_url,
            "ticket_no": ticket_no,
            "status": VisitStatus.ESPERA,
        }
        return await self.visit_repo.create(visit_data, responsible_snapshot=responsible_person)

    async def _resolve_fiscal(self, fiscal_identifier: str | None):
        if fiscal_identifier is None:
            return None
        value = fiscal_identifier.strip()
        if not value:
            return None

        # Accept local integer id or external UUID/id from source system.
        if value.isdigit():
            return await self.fiscal_repo.get_by_id(int(value))
        return await self.fiscal_repo.get_by_external_id(value)

    async def list(
        self,
        *,
        contributor_id: int | None = None,
        rif: str | None = None,
        cedula: str | None = None,
        status: str | None = None,
        fiscal_id: int | None = None,
        entry_date: date | None = None,
        open_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Visit]:
        if cedula:
            contributor = await self.contributor_repo.get_by_cedula(cedula.strip())
            if contributor is None:
                return []
            if contributor_id is not None and contributor.id != contributor_id:
                return []
            contributor_id = contributor.id
        return await self.visit_repo.list(
            contributor_id=contributor_id,
            rif=rif,
            status=status,
            fiscal_id=fiscal_id,
            entry_date=entry_date,
            open_only=open_only,
            skip=skip,
            limit=limit,
        )

    async def get(self, visit_id: UUID) -> Visit | None:
        return await self.visit_repo.get(visit_id)

    async def list_queue(self, *, department: str | None = None) -> list[Visit]:
        return await self.visit_repo.list_queue(department=department)

    async def call(self, visit_id: UUID, *, at: datetime | None = None) -> Visit | None:
        visit = await self.visit_repo.get(visit_id)
        if visit is None:
            return None
        if visit.status != VisitStatus.ESPERA:
            raise VisitFlowError("Solo se puede llamar una visita en espera")
        return await self.visit_repo.update(
            visit_id,
            {
                "status": VisitStatus.EN_ATENCION,
                "called_at": at or datetime.now(UTC),
            },
        )

    async def close(
        self,
        visit_id: UUID,
        body: VisitClose,
        *,
        at: datetime | None = None,
    ) -> Visit | None:
        visit = await self.visit_repo.get(visit_id)
        if visit is None:
            return None
        if visit.status != VisitStatus.EN_ATENCION:
            raise VisitFlowError("Solo se puede cerrar una visita en atención")
        if body.status not in CLOSE_STATUSES:
            raise VisitFlowError("status debe ser atendido, incompleto o remitido")
        contributor = await self.contributor_repo.get(visit.contributor_id)
        name = (contributor.name or "").strip() if contributor is not None else ""
        reason = (visit.reason or "").strip()
        if not name or not reason:
            raise VisitFlowError("Nombre y motivo son obligatorios para cerrar el turno")
        payload: dict[str, Any] = {
            "status": body.status,
            "closed_at": at or datetime.now(UTC),
        }
        if body.observations is not None:
            payload["observations"] = body.observations
        return await self.visit_repo.update(visit_id, payload)

    async def intake(self, visit_id: UUID, body: VisitIntake) -> Visit | None:
        visit = await self.visit_repo.get(visit_id)
        if visit is None:
            return None
        contributor = await self.contributor_repo.get(visit.contributor_id)
        if contributor is None:
            raise VisitFlowError("Contribuyente no encontrado")
        contributor_payload: dict[str, Any] = {"name": body.name}
        if body.rif is not None:
            existing = await self.contributor_repo.get_by_rif(body.rif)
            if existing is not None and existing.id != contributor.id:
                raise ContributorRifConflict("El RIF ya está registrado en otro contribuyente")
            contributor_payload["rif"] = body.rif
        try:
            updated_contributor = await self.contributor_repo.update(
                visit.contributor_id, contributor_payload
            )
        except IntegrityError as exc:
            raise ContributorRifConflict(
                "El RIF ya está registrado en otro contribuyente"
            ) from exc
        if updated_contributor is None:
            raise VisitFlowError("Contribuyente no encontrado")
        return await self.visit_repo.update(visit_id, {"reason": body.reason})

    async def register_exit(
        self,
        visit_id: UUID,
        exit_data: VisitUpdateExit,
        *,
        at: datetime | None = None,
    ) -> Visit | None:
        visit = await self.visit_repo.get(visit_id)
        if visit is None:
            return None
        if visit.status == VisitStatus.FINALIZADO:
            raise VisitFlowError("La visita ya está finalizada")
        if visit.status not in EXIT_ALLOWED_STATUSES:
            raise VisitFlowError("No se puede registrar salida desde el estado actual")

        now = at or datetime.now(UTC)
        try:
            local = now.astimezone(VENEZUELA_TZ)
        except (OSError, ZoneInfoNotFoundError, ValueError):
            local = now
        payload: dict[str, Any] = {
            "exit_at": now,
            "exit_date": exit_data.exit_date if exit_data.exit_date is not None else local.date(),
            "exit_time": (
                exit_data.exit_time
                if exit_data.exit_time is not None
                else local.time().replace(tzinfo=None, microsecond=0)
            ),
            "status": VisitStatus.FINALIZADO,
        }
        return await self.visit_repo.update(visit_id, payload)

    async def day_metrics(self, target_date: date) -> VisitDayMetrics:
        visits = await self.visit_repo.list_by_entry_date(target_date)
        waiting = 0
        in_service = 0
        closed = 0
        exited = 0
        waits: list[int] = []
        attentions: list[int] = []
        stays: list[int] = []
        for visit in visits:
            if visit.status == VisitStatus.ESPERA:
                waiting += 1
            elif visit.status == VisitStatus.EN_ATENCION:
                in_service += 1
            elif visit.status in CLOSE_STATUSES:
                closed += 1
            elif visit.status == VisitStatus.FINALIZADO:
                exited += 1
            metrics = visit_duration_metrics(
                entry_date=visit.entry_date,
                entry_time=visit.entry_time,
                called_at=visit.called_at,
                closed_at=visit.closed_at,
                exit_at=visit.exit_at,
            )
            if metrics["wait_seconds"] is not None:
                waits.append(metrics["wait_seconds"])
            if metrics["attention_seconds"] is not None:
                attentions.append(metrics["attention_seconds"])
            if metrics["stay_seconds"] is not None:
                stays.append(metrics["stay_seconds"])
        return VisitDayMetrics(
            target_date=target_date,
            waiting=waiting,
            in_service=in_service,
            closed=closed,
            exited=exited,
            avg_wait_seconds=_average(waits),
            avg_attention_seconds=_average(attentions),
            avg_stay_seconds=_average(stays),
        )

    async def update(self, visit_id: UUID, visit_data: VisitUpdate) -> Visit | None:
        payload = visit_data.model_dump(exclude_unset=True)
        payload.pop("status", None)
        fiscal_identifier = payload.get("fiscal_id")
        if fiscal_identifier is not None:
            fiscal = await self._resolve_fiscal(fiscal_identifier)
            if fiscal is None:
                raise ValueError("Fiscal no existe")
            if not fiscal.status:
                raise ValueError("Fiscal inactivo")
            payload["fiscal_id"] = fiscal.id
        return await self.visit_repo.update(visit_id, payload)

    async def mark_as_attended(self, visit_id: UUID) -> Visit | None:
        return await self.visit_repo.mark_as_attended(visit_id)

    async def soft_delete(self, visit_id: UUID) -> Visit | None:
        return await self.visit_repo.soft_delete(visit_id)

    async def history(
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
        return await self.visit_repo.list_history(
            rif=rif,
            contributor_name=contributor_name,
            file_number=file_number,
            department=department,
            date_from=date_from,
            date_to=date_to,
            status_list=status_list,
            skip=skip,
            limit=limit,
        )

    async def history_count(
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
        return await self.visit_repo.count_history(
            rif=rif,
            contributor_name=contributor_name,
            file_number=file_number,
            department=department,
            date_from=date_from,
            date_to=date_to,
            status_list=status_list,
        )
