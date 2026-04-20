from typing import Protocol
from uuid import UUID

from src.models.photo import Photo


class PhotoRepository(Protocol):
    async def create(self, visit_id: UUID, photo_url: str) -> Photo:
        """Create a photo row for a visit."""

    async def list_by_visit(self, visit_id: UUID) -> list[Photo]:
        """Return photos for a visit."""
