from typing import Any, Protocol

from src.models.contributor import Contributor


class ContributorRepository(Protocol):
    async def get(self, contributor_id: int) -> Contributor | None:
        """Return contributor by id."""

    async def get_by_name(self, name: str) -> Contributor | None:
        """Return contributor by exact name."""

    async def get_by_rif(self, rif: str) -> Contributor | None:
        """Return contributor by RIF (unique when not NULL)."""

    async def get_by_cedula(self, cedula: str) -> Contributor | None:
        """Return contributor by cédula (unique when not NULL)."""

    async def get_or_create_by_rif(self, rif: str, name: str) -> Contributor:
        """Return existing contributor by RIF or create one with the given real RIF and name."""

    async def get_or_create_by_cedula(
        self,
        cedula: str,
        *,
        name: str | None = None,
        rif: str | None = None,
    ) -> Contributor:
        """Return existing contributor by cédula or create a minimal row (rif/name optional)."""

    async def update(self, contributor_id: int, data: dict[str, Any]) -> Contributor | None:
        """Partial update of contributor fields."""
