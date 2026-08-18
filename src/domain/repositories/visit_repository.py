from __future__ import annotations

from datetime import date
from typing import Any, Protocol
from uuid import UUID

from src.models.visit import Visit, VisitStatus


class VisitRepository(Protocol):
    async def create(self, visit_data: dict, responsible_snapshot: str) -> Visit:
        """Create a visit row."""

    async def get(self, visit_id: UUID) -> Visit | None:
        """Get visit by id."""

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
        """List visits with optional filters. open_only = sin exit_at y no finalizado."""

    async def update(self, visit_id: UUID, visit_data: dict[str, Any]) -> Visit | None:
        """Update editable visit fields."""

    async def mark_as_attended(self, visit_id: UUID) -> Visit | None:
        """Mark visit as attended (status espera -> atendido)."""

    async def soft_delete(self, visit_id: UUID) -> Visit | None:
        """Soft delete visit setting deleted_at timestamp."""
    
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
        """List visits history with report-friendly columns."""

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
        """Count visits history using same filters."""

    async def allocate_next_ticket(self, entry_date: date) -> str:
        """Lock + next T-YYYYMMDD-NNNN for that date (incluye borradas)."""

    async def list_queue(self, *, department: str | None = None) -> list[Visit]:
        """Visitas en espera y en atención, FIFO por created_at."""

    async def list_by_entry_date(self, target_date: date) -> list[Visit]:
        """Visitas activas del día de ingreso (sin paginar)."""
