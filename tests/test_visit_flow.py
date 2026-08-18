from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.models.contributor import Contributor, ContributorType
from src.models.fiscal import Fiscal
from src.models.visit import (
    EXIT_ALLOWED_STATUSES,
    ON_PREMISES_STATUSES,
    Visit,
    VisitClose,
    VisitCreate,
    VisitIntake,
    VisitPublic,
    VisitStatus,
    VisitUpdate,
    VisitUpdateExit,
    format_ticket_no,
)
from src.services.visit_service import (
    ContributorRifConflict,
    VisitFlowError,
    VisitService,
    resolve_visit_list_entry_date,
)

ENTRY_DAY = date(2026, 8, 17)
ENTRY_TIME = time(8, 0, 0)


class FakeContributorRepository:
    def __init__(self) -> None:
        demo = Contributor(
            id=1,
            rif="J-12345678-9",
            cedula="V12345678",
            name="Contribuyente Demo",
            type=ContributorType.JURIDICA,
        )
        self._by_id: dict[int, Contributor] = {1: demo}
        self._next_id = 2
        self.contributor = demo

    def _register(self, contributor: Contributor) -> Contributor:
        if contributor.id is None:
            contributor.id = self._next_id
            self._next_id += 1
        self._by_id[contributor.id] = contributor
        return contributor

    async def get(self, contributor_id: int) -> Contributor | None:
        return self._by_id.get(contributor_id)

    async def get_by_name(self, name: str) -> Contributor | None:
        needle = name.strip().lower()
        for item in self._by_id.values():
            if item.name and item.name.strip().lower() == needle:
                return item
        return None

    async def get_by_rif(self, rif: str) -> Contributor | None:
        normalized = rif.strip()
        for item in self._by_id.values():
            if item.rif == normalized:
                return item
        return None

    async def get_by_cedula(self, cedula: str) -> Contributor | None:
        normalized = cedula.strip()
        for item in self._by_id.values():
            if item.cedula == normalized:
                return item
        return None

    async def get_or_create_by_rif(self, rif: str, name: str) -> Contributor:
        existing = await self.get_by_rif(rif)
        if existing:
            return existing
        return self._register(
            Contributor(
                rif=rif.strip(),
                name=name.strip(),
                type=ContributorType.NATURAL,
            )
        )

    async def get_or_create_by_cedula(
        self,
        cedula: str,
        *,
        name: str | None = None,
        rif: str | None = None,
    ) -> Contributor:
        existing = await self.get_by_cedula(cedula)
        if existing:
            return existing
        if rif and rif.strip().upper().startswith("TEMP-"):
            raise ValueError("RIF temporal no permitido en registro de visita")
        return self._register(
            Contributor(
                cedula=cedula.strip(),
                rif=rif.strip() if rif else None,
                name=name.strip() if name else None,
                type=ContributorType.NATURAL,
            )
        )

    async def update(self, contributor_id: int, data: dict[str, Any]) -> Contributor | None:
        contributor = self._by_id.get(contributor_id)
        if contributor is None:
            return None
        for field_name, value in data.items():
            setattr(contributor, field_name, value)
        return contributor


class FakeFiscalRepository:
    def __init__(self) -> None:
        self.fiscal = Fiscal(id=7, external_id="ext-7", name="Fiscal Demo", status=True)

    async def upsert_many(self, fiscals: list[dict]) -> tuple[int, int]:
        return (0, 0)

    async def search(
        self, query: str | None = None, skip: int = 0, limit: int = 100
    ) -> list[Fiscal]:
        return [self.fiscal]

    async def get_by_id(self, fiscal_id: int) -> Fiscal | None:
        return self.fiscal if fiscal_id == self.fiscal.id else None

    async def get_by_external_id(self, external_id: str) -> Fiscal | None:
        return self.fiscal if external_id == self.fiscal.external_id else None


class InMemoryVisitRepository:
    def __init__(self) -> None:
        self._items: dict[UUID, Visit] = {}
        self._ticket_seq: dict[date, int] = {}
        self._ticket_lock = asyncio.Lock()

    def _active(self, visit: Visit) -> bool:
        return visit.deleted_at is None

    async def create(self, visit_data: dict, responsible_snapshot: str) -> Visit:
        payload = dict(visit_data)
        ticket_no = payload.get("ticket_no")
        if ticket_no and any(item.ticket_no == ticket_no for item in self._items.values()):
            raise IntegrityError(
                "INSERT",
                {},
                Exception("duplicate key value violates unique constraint ix_visit_ticket_no"),
            )
        payload.setdefault("id", uuid4())
        payload.setdefault("status", VisitStatus.ESPERA)
        payload["received_by"] = responsible_snapshot
        visit = Visit(**payload)
        visit.status = VisitStatus.ESPERA
        visit.received_by = responsible_snapshot
        if visit.created_at is None:
            visit.created_at = datetime.now(UTC)
        self._items[visit.id] = visit
        return visit

    async def get(self, visit_id: UUID) -> Visit | None:
        visit = self._items.get(visit_id)
        if visit is None or not self._active(visit):
            return None
        return visit

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
        items = [visit for visit in self._items.values() if self._active(visit)]
        if contributor_id is not None:
            items = [visit for visit in items if visit.contributor_id == contributor_id]
        if fiscal_id is not None:
            items = [visit for visit in items if visit.fiscal_id == fiscal_id]
        if status is not None:
            items = [visit for visit in items if visit.status == status]
        if entry_date is not None:
            items = [visit for visit in items if visit.entry_date == entry_date]
        if open_only:
            items = [
                visit
                for visit in items
                if visit.exit_at is None and visit.status != VisitStatus.FINALIZADO
            ]
        items.sort(key=lambda visit: visit.created_at or datetime.min, reverse=True)
        return items[skip : skip + limit]

    async def update(self, visit_id: UUID, visit_data: dict[str, Any]) -> Visit | None:
        visit = await self.get(visit_id)
        if visit is None:
            return None
        for field_name, value in visit_data.items():
            setattr(visit, field_name, value)
        visit.updated_at = datetime.now(UTC)
        return visit

    async def mark_as_attended(self, visit_id: UUID) -> Visit | None:
        visit = await self.get(visit_id)
        if visit is None or visit.status != VisitStatus.ESPERA:
            return None
        visit.status = VisitStatus.ATENDIDO
        return visit

    async def soft_delete(self, visit_id: UUID) -> Visit | None:
        visit = await self.get(visit_id)
        if visit is None:
            return None
        visit.deleted_at = datetime.now(UTC)
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
        return []

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
        return 0

    def _max_ticket_sequence(self, entry_date: date) -> int:
        prefix = f"T-{entry_date.strftime('%Y%m%d')}-"
        max_seq = 0
        for visit in self._items.values():
            ticket_no = visit.ticket_no or ""
            if not ticket_no.startswith(prefix):
                continue
            suffix = ticket_no[len(prefix) :]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
        return max_seq

    async def allocate_next_ticket(self, entry_date: date) -> str:
        async with self._ticket_lock:
            current = self._ticket_seq.get(entry_date)
            if current is None:
                current = self._max_ticket_sequence(entry_date)
            next_seq = current + 1
            self._ticket_seq[entry_date] = next_seq
            return format_ticket_no(entry_date, next_seq)

    async def list_queue(self, *, department: str | None = None) -> list[Visit]:
        statuses = {VisitStatus.ESPERA, VisitStatus.EN_ATENCION}
        items = [
            visit
            for visit in self._items.values()
            if self._active(visit) and visit.status in statuses
        ]
        if department is not None:
            items = [visit for visit in items if visit.department == department]
        items.sort(key=lambda visit: visit.created_at or datetime.min)
        return items

    async def list_by_entry_date(self, target_date: date) -> list[Visit]:
        return [
            visit
            for visit in self._items.values()
            if self._active(visit) and visit.entry_date == target_date
        ]


def _create_payload(**overrides: Any) -> VisitCreate:
    data = {
        "contributor_cedula": "V12345678",
        "contributor_rif": "J-12345678-9",
        "contributor_name": "Contribuyente Demo",
        "fiscal_id": "7",
        "responsible_person": "Operador Garita",
        "reason": "Declaración",
        "department": "Taquilla",
        "entry_date": ENTRY_DAY,
        "entry_time": ENTRY_TIME,
    }
    data.update(overrides)
    return VisitCreate(**data)


def _gate_payload(**overrides: Any) -> VisitCreate:
    data = {
        "contributor_cedula": "V87654321",
        "department": "Taquilla",
        "entry_date": ENTRY_DAY,
        "entry_time": ENTRY_TIME,
        "responsible_person": "Operador Garita",
    }
    data.update(overrides)
    return VisitCreate(**data)


def _service() -> tuple[VisitService, InMemoryVisitRepository]:
    repo = InMemoryVisitRepository()
    service = VisitService(
        contributor_repo=FakeContributorRepository(),
        fiscal_repo=FakeFiscalRepository(),
        visit_repo=repo,
    )
    return service, repo


@pytest.mark.asyncio
async def test_create_assigns_ticket_and_leaves_espera() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    assert visit.status == VisitStatus.ESPERA
    assert visit.ticket_no == "T-20260817-0001"


@pytest.mark.asyncio
async def test_ticket_no_increments_on_the_same_day() -> None:
    service, _ = _service()
    first = await service.create(_create_payload())
    second = await service.create(_create_payload(reason="Seguimiento"))
    other_day = await service.create(_create_payload(entry_date=date(2026, 8, 18)))
    assert first.ticket_no == "T-20260817-0001"
    assert second.ticket_no == "T-20260817-0002"
    assert other_day.ticket_no == "T-20260818-0001"


@pytest.mark.asyncio
async def test_call_from_espera_sets_called_at_and_en_atencion() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    called_at = datetime(2026, 8, 17, 12, 30, tzinfo=UTC)
    updated = await service.call(visit.id, at=called_at)
    assert updated is not None
    assert updated.status == VisitStatus.EN_ATENCION
    assert updated.called_at == called_at


@pytest.mark.asyncio
async def test_call_from_other_status_fails() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    await service.call(visit.id, at=datetime(2026, 8, 17, 12, 30, tzinfo=UTC))
    with pytest.raises(VisitFlowError):
        await service.call(visit.id)


@pytest.mark.asyncio
async def test_close_from_en_atencion_sets_closed_at() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    await service.call(visit.id, at=datetime(2026, 8, 17, 12, 30, tzinfo=UTC))
    closed_at = datetime(2026, 8, 17, 13, 0, tzinfo=UTC)
    updated = await service.close(
        visit.id,
        VisitClose(status=VisitStatus.ATENDIDO, observations="Listo"),
        at=closed_at,
    )
    assert updated is not None
    assert updated.status == VisitStatus.ATENDIDO
    assert updated.closed_at == closed_at
    assert updated.observations == "Listo"


@pytest.mark.asyncio
async def test_close_from_espera_fails() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    with pytest.raises(VisitFlowError):
        await service.close(visit.id, VisitClose(status=VisitStatus.ATENDIDO))


@pytest.mark.asyncio
async def test_exit_from_atendido_sets_exit_at_and_finalizado() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    await service.call(visit.id, at=datetime(2026, 8, 17, 12, 30, tzinfo=UTC))
    await service.close(
        visit.id,
        VisitClose(status=VisitStatus.ATENDIDO),
        at=datetime(2026, 8, 17, 13, 0, tzinfo=UTC),
    )
    exit_at = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)
    updated = await service.register_exit(
        visit.id,
        VisitUpdateExit(exit_date=ENTRY_DAY, exit_time=time(10, 0, 0)),
        at=exit_at,
    )
    assert updated is not None
    assert updated.status == VisitStatus.FINALIZADO
    assert updated.exit_at == exit_at
    assert updated.exit_date == ENTRY_DAY
    assert updated.exit_time == time(10, 0, 0)


@pytest.mark.asyncio
async def test_wait_attention_stay_metrics_with_fixed_timestamps() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    await service.call(visit.id, at=datetime(2026, 8, 17, 12, 30, tzinfo=UTC))
    await service.close(
        visit.id,
        VisitClose(status=VisitStatus.ATENDIDO),
        at=datetime(2026, 8, 17, 13, 0, tzinfo=UTC),
    )
    await service.register_exit(
        visit.id,
        VisitUpdateExit(),
        at=datetime(2026, 8, 17, 14, 0, tzinfo=UTC),
    )
    public = VisitPublic.model_validate(await service.get(visit.id))
    assert public.wait_seconds == 1800
    assert public.attention_seconds == 1800
    assert public.stay_seconds == 7200


@pytest.mark.asyncio
async def test_queue_is_fifo_by_department() -> None:
    service, repo = _service()
    first = await service.create(_create_payload(reason="Primero", department="Taquilla"))
    second = await service.create(_create_payload(reason="Segundo", department="Taquilla"))
    other = await service.create(_create_payload(reason="Otro", department="Gerencia"))
    repo._items[first.id].created_at = datetime(2026, 8, 17, 10, 5)
    repo._items[second.id].created_at = datetime(2026, 8, 17, 10, 0)
    repo._items[other.id].created_at = datetime(2026, 8, 17, 9, 0)

    queue = await service.list_queue(department="Taquilla")
    assert [item.id for item in queue] == [second.id, first.id]
    assert all(item.department == "Taquilla" for item in queue)


@pytest.mark.asyncio
async def test_concurrent_creates_get_distinct_same_day_tickets() -> None:
    service, _ = _service()
    first, second = await asyncio.gather(
        service.create(_create_payload(reason="A")),
        service.create(_create_payload(reason="B")),
    )
    assert {first.ticket_no, second.ticket_no} == {"T-20260817-0001", "T-20260817-0002"}


@pytest.mark.asyncio
async def test_create_retries_ticket_unique_integrity_error() -> None:
    service, repo = _service()
    original_allocate = repo.allocate_next_ticket
    calls = {"n": 0}

    async def colliding_allocate(entry_date: date) -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            return f"T-{entry_date.strftime('%Y%m%d')}-0001"
        return await original_allocate(entry_date)

    repo.allocate_next_ticket = colliding_allocate  # type: ignore[method-assign]
    first = await service.create(_create_payload(reason="Primera"))
    second = await service.create(_create_payload(reason="Segunda"))
    assert first.ticket_no == "T-20260817-0001"
    assert second.ticket_no == "T-20260817-0002"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_update_with_status_in_payload_does_not_change_status() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    updated = await service.update(
        visit.id,
        VisitUpdate.model_validate({"reason": "Corrección", "status": "finalizado"}),
    )
    assert "status" not in VisitUpdate.model_fields
    assert updated is not None
    assert updated.status == VisitStatus.ESPERA
    assert updated.reason == "Corrección"


@pytest.mark.asyncio
async def test_exit_missing_visit_returns_none() -> None:
    service, _ = _service()
    result = await service.register_exit(uuid4(), VisitUpdateExit())
    assert result is None


@pytest.mark.asyncio
async def test_exit_forces_finalizado_ignoring_body_status() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    updated = await service.register_exit(
        visit.id,
        VisitUpdateExit(
            status=VisitStatus.ATENDIDO,
            exit_date=ENTRY_DAY,
            exit_time=time(10, 0, 0),
        ),
    )
    assert updated is not None
    assert updated.status == VisitStatus.FINALIZADO


def test_on_premises_statuses_includes_desk_states() -> None:
    assert {
        VisitStatus.ESPERA,
        VisitStatus.EN_ATENCION,
        VisitStatus.ATENDIDO,
        VisitStatus.INCOMPLETO,
        VisitStatus.REMITIDO,
    } == ON_PREMISES_STATUSES
    assert VisitStatus.FINALIZADO not in ON_PREMISES_STATUSES
    assert VisitStatus.EN_ATENCION in EXIT_ALLOWED_STATUSES


def test_open_list_does_not_default_entry_date_to_today() -> None:
    today = date(2026, 8, 17)
    assert resolve_visit_list_entry_date(entry_date=None, open_only=True, today=today) is None
    assert resolve_visit_list_entry_date(entry_date=None, open_only=False, today=today) == today
    assert (
        resolve_visit_list_entry_date(entry_date=date(2026, 1, 1), open_only=True, today=today)
        == date(2026, 1, 1)
    )


@pytest.mark.asyncio
async def test_create_with_cedula_only_skips_rif_name_reason() -> None:
    service, _ = _service()
    visit = await service.create(_gate_payload())
    contributor = await service.contributor_repo.get(visit.contributor_id)
    assert visit.status == VisitStatus.ESPERA
    assert visit.ticket_no == "T-20260817-0001"
    assert visit.reason is None
    assert visit.fiscal_id is None
    assert contributor is not None
    assert contributor.cedula == "V87654321"
    assert contributor.rif is None
    assert contributor.name is None


@pytest.mark.asyncio
async def test_create_reuses_contributor_by_cedula() -> None:
    service, _ = _service()
    first = await service.create(_gate_payload())
    second = await service.create(_gate_payload(department="Gerencia"))
    assert first.contributor_id == second.contributor_id
    assert len(service.contributor_repo._by_id) == 2  # demo + nuevo


@pytest.mark.asyncio
async def test_intake_updates_contributor_and_reason() -> None:
    service, _ = _service()
    visit = await service.create(_gate_payload())
    updated = await service.intake(
        visit.id,
        VisitIntake(name="Ana Pérez", reason="Devolución", rif="J-11111111-1"),
    )
    contributor = await service.contributor_repo.get(visit.contributor_id)
    assert updated is not None
    assert updated.reason == "Devolución"
    assert contributor is not None
    assert contributor.name == "Ana Pérez"
    assert contributor.rif == "J-11111111-1"


@pytest.mark.asyncio
async def test_intake_rif_unique_conflict() -> None:
    service, _ = _service()
    visit = await service.create(_gate_payload())
    with pytest.raises(ContributorRifConflict):
        await service.intake(
            visit.id,
            VisitIntake(name="Otro", reason="Consulta", rif="J-12345678-9"),
        )


@pytest.mark.asyncio
async def test_close_without_name_or_reason_rejected() -> None:
    service, _ = _service()
    visit = await service.create(_gate_payload())
    await service.call(visit.id, at=datetime(2026, 8, 17, 12, 30, tzinfo=UTC))
    with pytest.raises(VisitFlowError):
        await service.close(visit.id, VisitClose(status=VisitStatus.ATENDIDO))


@pytest.mark.asyncio
async def test_exit_from_en_atencion_sets_finalizado() -> None:
    service, _ = _service()
    visit = await service.create(_create_payload())
    await service.call(visit.id, at=datetime(2026, 8, 17, 12, 30, tzinfo=UTC))
    exit_at = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)
    updated = await service.register_exit(visit.id, VisitUpdateExit(), at=exit_at)
    assert updated is not None
    assert updated.status == VisitStatus.FINALIZADO
    assert updated.exit_at == exit_at
    public = VisitPublic.model_validate(updated)
    assert public.stay_seconds == 7200


@pytest.mark.asyncio
async def test_list_open_by_cedula_is_not_limited_to_today() -> None:
    service, _ = _service()
    older_open = await service.create(_gate_payload(entry_date=date(2026, 8, 10)))
    closed_today = await service.create(_gate_payload())
    await service.register_exit(
        closed_today.id,
        VisitUpdateExit(),
        at=datetime(2026, 8, 17, 18, 0, tzinfo=UTC),
    )
    items = await service.list(cedula="V87654321", open_only=True, entry_date=None)
    ids = {item.id for item in items}
    assert older_open.id in ids
    assert closed_today.id not in ids


@pytest.mark.asyncio
async def test_visit_public_includes_nullable_contributor_identity() -> None:
    service, _ = _service()
    visit = await service.create(_gate_payload())
    contributor = await service.contributor_repo.get(visit.contributor_id)
    assert contributor is not None
    public = VisitPublic.model_validate(
        visit,
        update={
            "contributor_cedula": contributor.cedula,
            "contributor_rif": contributor.rif,
            "contributor_name": contributor.name,
        },
    )
    assert public.contributor_cedula == "V87654321"
    assert public.contributor_rif is None
    assert public.contributor_name is None
