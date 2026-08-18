from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.domain.repositories.asset_repository import AssetRepository
from src.models.asset import (
    AssetAssignment,
    AssetMovement,
    AssetMovementDirection,
    AssetMovementStatus,
    AssetStatus,
    SeniatAsset,
)


class PostgresAssetRepository(AssetRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> SeniatAsset:
        asset = SeniatAsset(**data)
        asset.status = AssetStatus.IN_SEDE
        self.session.add(asset)
        await self.session.flush()
        await self.session.refresh(asset)
        return asset

    async def get(self, asset_id: UUID) -> SeniatAsset | None:
        result = await self.session.execute(select(SeniatAsset).where(SeniatAsset.id == asset_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        status: AssetStatus | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SeniatAsset]:
        statement = select(SeniatAsset)
        if status is not None:
            statement = statement.where(SeniatAsset.status == status)
        if q:
            term = f"%{q.strip()}%"
            statement = statement.where(
                or_(
                    SeniatAsset.inventory_code.ilike(term),
                    SeniatAsset.serial.ilike(term),
                    SeniatAsset.brand.ilike(term),
                )
            )
        statement = statement.order_by(SeniatAsset.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update(self, asset_id: UUID, data: dict[str, Any]) -> SeniatAsset | None:
        asset = await self.get(asset_id)
        if asset is None:
            return None
        for field_name, value in data.items():
            setattr(asset, field_name, value)
        asset.updated_at = datetime.utcnow()
        self.session.add(asset)
        await self.session.flush()
        return await self.get(asset_id)

    async def delete(self, asset_id: UUID) -> bool:
        asset = await self.get(asset_id)
        if asset is None:
            return False
        await self.session.execute(
            delete(AssetAssignment).where(AssetAssignment.asset_id == asset_id)
        )
        await self.session.execute(delete(AssetMovement).where(AssetMovement.asset_id == asset_id))
        await self.session.execute(delete(SeniatAsset).where(SeniatAsset.id == asset_id))
        await self.session.flush()
        return True

    async def get_active_assignment(self, asset_id: UUID) -> AssetAssignment | None:
        statement = (
            select(AssetAssignment)
            .where(
                AssetAssignment.asset_id == asset_id,
                AssetAssignment.released_at.is_(None),
            )
            .order_by(AssetAssignment.assigned_at.desc())
        )
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def create_assignment(self, data: dict) -> AssetAssignment:
        assignment = AssetAssignment(**data)
        self.session.add(assignment)
        await self.session.flush()
        await self.session.refresh(assignment)
        return assignment

    async def close_assignment(
        self, assignment_id: int, *, released_at: datetime
    ) -> AssetAssignment | None:
        result = await self.session.execute(
            select(AssetAssignment).where(AssetAssignment.id == assignment_id)
        )
        assignment = result.scalar_one_or_none()
        if assignment is None:
            return None
        assignment.released_at = released_at
        self.session.add(assignment)
        await self.session.flush()
        await self.session.refresh(assignment)
        return assignment

    async def get_open_out_movement(self, asset_id: UUID) -> AssetMovement | None:
        statement = select(AssetMovement).where(
            AssetMovement.asset_id == asset_id,
            AssetMovement.direction == AssetMovementDirection.OUT,
            AssetMovement.status == AssetMovementStatus.OPEN,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create_movement(self, data: dict) -> AssetMovement:
        movement = AssetMovement(**data)
        self.session.add(movement)
        await self.session.flush()
        await self.session.refresh(movement)
        return movement

    async def close_movement(
        self, movement_id: UUID, *, closed_at: datetime
    ) -> AssetMovement | None:
        result = await self.session.execute(
            select(AssetMovement).where(AssetMovement.id == movement_id)
        )
        movement = result.scalar_one_or_none()
        if movement is None:
            return None
        movement.status = AssetMovementStatus.CLOSED
        movement.closed_at = closed_at
        self.session.add(movement)
        await self.session.flush()
        await self.session.refresh(movement)
        return movement

    async def list_open_out(self, *, visit_id: UUID | None = None) -> list[AssetMovement]:
        statement = select(AssetMovement).where(
            AssetMovement.direction == AssetMovementDirection.OUT,
            AssetMovement.status == AssetMovementStatus.OPEN,
        )
        if visit_id is not None:
            statement = statement.where(AssetMovement.visit_id == visit_id)
        statement = statement.order_by(AssetMovement.opened_at.asc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())
