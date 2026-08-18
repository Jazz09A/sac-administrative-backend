from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from src.models.asset import (
    AssetAssignment,
    AssetMovement,
    AssetStatus,
    SeniatAsset,
)


class AssetRepository(Protocol):
    async def create(self, data: dict) -> SeniatAsset:
        """Persist a SENIAT institutional asset."""

    async def get(self, asset_id: UUID) -> SeniatAsset | None:
        """Get asset by id."""

    async def list(
        self,
        *,
        status: AssetStatus | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SeniatAsset]:
        """List assets with optional status and text filters."""

    async def update(self, asset_id: UUID, data: dict[str, Any]) -> SeniatAsset | None:
        """Update asset fields."""

    async def delete(self, asset_id: UUID) -> bool:
        """Hard-delete asset and related assignments/movements."""

    async def get_active_assignment(self, asset_id: UUID) -> AssetAssignment | None:
        """Return the assignment that has not been released."""

    async def create_assignment(self, data: dict) -> AssetAssignment:
        """Create an assignment row."""

    async def close_assignment(
        self, assignment_id: int, *, released_at: datetime
    ) -> AssetAssignment | None:
        """Set released_at on an assignment."""

    async def get_open_out_movement(self, asset_id: UUID) -> AssetMovement | None:
        """Return the open outbound movement, if any."""

    async def create_movement(self, data: dict) -> AssetMovement:
        """Create a movement row."""

    async def close_movement(
        self, movement_id: UUID, *, closed_at: datetime
    ) -> AssetMovement | None:
        """Close a movement (status closed + closed_at)."""

    async def list_open_out(self, *, visit_id: UUID | None = None) -> list[AssetMovement]:
        """List open outbound movements, optionally for one visit."""
