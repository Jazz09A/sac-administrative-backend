from typing import Protocol

from src.models.fiscal import Fiscal


class FiscalRepository(Protocol):
    async def upsert_many(self, fiscals: list[dict]) -> tuple[int, int]:
        """Upsert fiscals and return inserted, updated totals."""

    async def search(self, query: str | None = None, limit: int = 100) -> list[Fiscal]:
        """Search local fiscals cache."""

    async def get_by_id(self, fiscal_id: int) -> Fiscal | None:
        """Return fiscal by local id."""

    async def get_by_external_id(self, external_id: str) -> Fiscal | None:
        """Return fiscal by external UUID/id from source system."""
