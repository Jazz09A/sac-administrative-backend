from typing import Any, List, Protocol
from datetime import date
from uuid import UUID

from src.models.visit import Visit, VisitStatus, VisitUpdateExit


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
        skip: int = 0,
        limit: int = 100,
    ) -> list[Visit]:
        """List visits with optional filters."""

    async def register_exit(self, visit_id: UUID, exit_data: VisitUpdateExit) -> Visit | None:
        """Register visit exit."""

    async def mark_as_attended(self, visit_id: UUID) -> Visit | None:
        """Mark visit as attended (status espera -> atendido)."""

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
        """List visits history with report-friendly columns."""
