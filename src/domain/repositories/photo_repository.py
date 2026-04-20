from typing import Optional, Protocol
from uuid import UUID

from src.models.photo import Photo


class PhotoRepository(Protocol):
    async def create(
        self,
        visit_id: UUID,
        object_key: str,
        *,
        bucket: Optional[str] = None,
        content_type: Optional[str] = None,
        original_filename: Optional[str] = None,
        size: Optional[int] = None,
    ) -> Photo:
        """Create a photo row for a visit storing the object key and metadata."""

    async def list_by_visit(self, visit_id: UUID) -> list[Photo]:
        """Return photos for a visit."""
