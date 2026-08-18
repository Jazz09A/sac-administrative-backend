from __future__ import annotations

import inspect
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.models.asset import (
    AssetAssignment,
    AssetAssignRequest,
    AssetMovement,
    AssetMovementCreate,
    AssetMovementDirection,
    AssetMovementStatus,
    AssetStatus,
    SeniatAsset,
    SeniatAssetCreate,
)
from src.services import asset_service as asset_service_module
from src.services.asset_service import AssetFlowError, AssetService

CARRIER_ID = uuid4()
USER_ID = uuid4()


class InMemoryAssetRepository:
    def __init__(self) -> None:
        self._assets: dict[UUID, SeniatAsset] = {}
        self._assignments: dict[int, AssetAssignment] = {}
        self._movements: dict[UUID, AssetMovement] = {}
        self._assignment_seq = 0

    async def create(self, data: dict) -> SeniatAsset:
        payload = dict(data)
        payload.setdefault("id", uuid4())
        payload.setdefault("status", AssetStatus.IN_SEDE)
        asset = SeniatAsset(**payload)
        self._assets[asset.id] = asset
        return asset

    async def get(self, asset_id: UUID) -> SeniatAsset | None:
        return self._assets.get(asset_id)

    async def list(
        self,
        *,
        status: AssetStatus | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SeniatAsset]:
        items = list(self._assets.values())
        if status is not None:
            items = [asset for asset in items if asset.status == status]
        if q:
            term = q.strip().lower()
            items = [
                asset
                for asset in items
                if term in asset.inventory_code.lower()
                or (asset.serial is not None and term in asset.serial.lower())
                or (asset.brand is not None and term in asset.brand.lower())
            ]
        items.sort(key=lambda asset: asset.created_at or datetime.min, reverse=True)
        return items[skip : skip + limit]

    async def update(self, asset_id: UUID, data: dict[str, Any]) -> SeniatAsset | None:
        asset = await self.get(asset_id)
        if asset is None:
            return None
        for field_name, value in data.items():
            setattr(asset, field_name, value)
        asset.updated_at = datetime.now(UTC)
        return asset

    async def delete(self, asset_id: UUID) -> bool:
        if asset_id not in self._assets:
            return False
        self._assignments = {
            key: item for key, item in self._assignments.items() if item.asset_id != asset_id
        }
        self._movements = {
            key: item for key, item in self._movements.items() if item.asset_id != asset_id
        }
        del self._assets[asset_id]
        return True

    async def get_active_assignment(self, asset_id: UUID) -> AssetAssignment | None:
        actives = [
            item
            for item in self._assignments.values()
            if item.asset_id == asset_id and item.released_at is None
        ]
        actives.sort(key=lambda item: item.assigned_at, reverse=True)
        return actives[0] if actives else None

    async def create_assignment(self, data: dict) -> AssetAssignment:
        payload = dict(data)
        self._assignment_seq += 1
        payload.setdefault("id", self._assignment_seq)
        assignment = AssetAssignment(**payload)
        assert assignment.id is not None
        self._assignments[assignment.id] = assignment
        return assignment

    async def close_assignment(
        self, assignment_id: int, *, released_at: datetime
    ) -> AssetAssignment | None:
        assignment = self._assignments.get(assignment_id)
        if assignment is None:
            return None
        assignment.released_at = released_at
        return assignment

    async def get_open_out_movement(self, asset_id: UUID) -> AssetMovement | None:
        for movement in self._movements.values():
            if (
                movement.asset_id == asset_id
                and movement.direction == AssetMovementDirection.OUT
                and movement.status == AssetMovementStatus.OPEN
            ):
                return movement
        return None

    async def create_movement(self, data: dict) -> AssetMovement:
        payload = dict(data)
        payload.setdefault("id", uuid4())
        payload.setdefault("status", AssetMovementStatus.OPEN)
        movement = AssetMovement(**payload)
        self._movements[movement.id] = movement
        return movement

    async def close_movement(
        self, movement_id: UUID, *, closed_at: datetime
    ) -> AssetMovement | None:
        movement = self._movements.get(movement_id)
        if movement is None:
            return None
        movement.status = AssetMovementStatus.CLOSED
        movement.closed_at = closed_at
        return movement

    async def list_open_out(self, *, visit_id: UUID | None = None) -> list[AssetMovement]:
        items = [
            movement
            for movement in self._movements.values()
            if movement.direction == AssetMovementDirection.OUT
            and movement.status == AssetMovementStatus.OPEN
        ]
        if visit_id is not None:
            items = [movement for movement in items if movement.visit_id == visit_id]
        items.sort(key=lambda movement: movement.opened_at)
        return items


def _create_payload(**overrides: Any) -> SeniatAssetCreate:
    data = {
        "inventory_code": "BN-001",
        "serial": "SN-99",
        "brand": "Dell",
        "model": "Latitude",
        "category": "computacion",
    }
    data.update(overrides)
    return SeniatAssetCreate(**data)


def _movement_payload(**overrides: Any) -> AssetMovementCreate:
    data: dict[str, Any] = {
        "direction": AssetMovementDirection.OUT,
        "carrier_user_id": CARRIER_ID,
    }
    data.update(overrides)
    return AssetMovementCreate(**data)


def _service() -> tuple[AssetService, InMemoryAssetRepository]:
    repo = InMemoryAssetRepository()
    return AssetService(asset_repo=repo), repo


@pytest.mark.asyncio
async def test_create_persists_in_sede() -> None:
    service, _ = _service()
    asset = await service.create(_create_payload())
    assert asset.status == AssetStatus.IN_SEDE
    assert asset.inventory_code == "BN-001"
    assert asset.serial == "SN-99"
    assert asset.brand == "Dell"
    assert asset.model == "Latitude"


@pytest.mark.asyncio
async def test_assign_sets_assigned() -> None:
    service, _ = _service()
    asset = await service.create(_create_payload())
    updated = await service.assign(
        asset.id,
        AssetAssignRequest(user_id=USER_ID, workstation="Puesto 1"),
    )
    assert updated is not None
    assert updated.status == AssetStatus.ASSIGNED
    assert updated.assigned_user_id == USER_ID
    assert updated.workstation == "Puesto 1"


@pytest.mark.asyncio
async def test_out_opens_movement_and_sets_in_transit_out() -> None:
    service, _ = _service()
    asset = await service.create(_create_payload())
    await service.assign(asset.id, AssetAssignRequest(user_id=USER_ID))
    movement = await service.record_movement(asset.id, _movement_payload())
    refreshed = await service.get(asset.id)
    assert movement is not None
    assert movement.direction == AssetMovementDirection.OUT
    assert movement.status == AssetMovementStatus.OPEN
    assert movement.carrier_user_id == CARRIER_ID
    assert refreshed is not None
    assert refreshed.status == AssetStatus.IN_TRANSIT_OUT


@pytest.mark.asyncio
async def test_second_out_with_open_movement_fails() -> None:
    service, _ = _service()
    asset = await service.create(_create_payload())
    await service.record_movement(asset.id, _movement_payload())
    with pytest.raises(AssetFlowError):
        await service.record_movement(asset.id, _movement_payload(notes="segundo"))


@pytest.mark.asyncio
async def test_in_closes_open_and_returns_assigned_when_assignment_active() -> None:
    service, _ = _service()
    asset = await service.create(_create_payload())
    await service.assign(asset.id, AssetAssignRequest(user_id=USER_ID))
    opened = await service.record_movement(asset.id, _movement_payload())
    closed = await service.record_movement(
        asset.id,
        _movement_payload(direction=AssetMovementDirection.IN),
    )
    refreshed = await service.get(asset.id)
    assert opened is not None
    assert closed is not None
    assert closed.id == opened.id
    assert closed.status == AssetMovementStatus.CLOSED
    assert closed.closed_at is not None
    assert refreshed is not None
    assert refreshed.status == AssetStatus.ASSIGNED


@pytest.mark.asyncio
async def test_in_closes_open_and_returns_in_sede_when_no_assignment() -> None:
    service, _ = _service()
    asset = await service.create(_create_payload())
    await service.record_movement(asset.id, _movement_payload())
    await service.record_movement(
        asset.id,
        _movement_payload(direction=AssetMovementDirection.IN),
    )
    refreshed = await service.get(asset.id)
    assert refreshed is not None
    assert refreshed.status == AssetStatus.IN_SEDE


@pytest.mark.asyncio
async def test_alerts_list_open_out_and_clear_after_in() -> None:
    service, _ = _service()
    asset = await service.create(_create_payload())
    visit_id = uuid4()
    opened = await service.record_movement(
        asset.id,
        _movement_payload(visit_id=visit_id),
    )
    alerts = await service.list_open_out_alerts()
    by_visit = await service.list_open_out_alerts(visit_id=visit_id)
    assert opened is not None
    assert [item.id for item in alerts] == [opened.id]
    assert [item.id for item in by_visit] == [opened.id]
    await service.record_movement(
        asset.id,
        _movement_payload(direction=AssetMovementDirection.IN),
    )
    assert await service.list_open_out_alerts() == []
    assert await service.list_open_out_alerts(visit_id=visit_id) == []


def test_no_contributor_id_in_model_or_service() -> None:
    assert "contributor_id" not in SeniatAsset.model_fields
    assert "contributor_id" not in inspect.getsource(asset_service_module)


@pytest.mark.asyncio
async def test_delete_fails_when_open_movement() -> None:
    service, _ = _service()
    asset = await service.create(_create_payload())
    await service.record_movement(asset.id, _movement_payload())
    with pytest.raises(AssetFlowError):
        await service.delete(asset.id)
    assert await service.get(asset.id) is not None
