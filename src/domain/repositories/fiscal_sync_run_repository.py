from typing import Protocol

from src.models.fiscal import FiscalSyncRun


class FiscalSyncRunRepository(Protocol):
    async def start_run(self) -> FiscalSyncRun:
        """Create a sync run entry."""

    async def finish_run(
        self,
        run: FiscalSyncRun,
        *,
        status: str,
        fetched_total: int,
        inserted_total: int,
        updated_total: int,
        skipped_total: int,
        error_message: str | None = None,
    ) -> FiscalSyncRun:
        """Finalize sync run entry with totals."""

    async def get_last_run(self) -> FiscalSyncRun | None:
        """Return most recent sync run."""
