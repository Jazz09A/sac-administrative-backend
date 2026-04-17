from typing import Protocol

from src.models.contributor import Contributor


class ContributorRepository(Protocol):
    async def get(self, contributor_id: int) -> Contributor | None:
        """Return contributor by id."""

    async def get_by_name(self, name: str) -> Contributor | None:
        """Return contributor by exact name."""

    async def create_minimal(self, name: str) -> Contributor:
        """Create contributor with minimal required data."""
