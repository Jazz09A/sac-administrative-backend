from typing import Protocol
from datetime import date
from uuid import UUID

from src.models.visit import Visit, VisitUpdateExit


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
