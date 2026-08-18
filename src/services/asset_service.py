from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from src.core.image_type import sniff_image_content_type
from src.domain.repositories.asset_repository import AssetRepository
from src.domain.repositories.file_storage_repository import FileStorageRepository
from src.models.asset import (
    AssetAssignRequest,
    AssetMovement,
    AssetMovementCreate,
    AssetMovementDirection,
    AssetMovementStatus,
    AssetStatus,
    SeniatAsset,
    SeniatAssetCreate,
    SeniatAssetUpdate,
)

_EXPORT_LIMIT = 100_000
_MAX_PHOTO_BYTES = 10 * 1024 * 1024
_PHOTO_PREFIX = "sac-administrative/seniat-assets"


class AssetFlowError(ValueError):
    """Transición inválida en el flujo de bienes nacionales SENIAT."""


class AssetService:
    def __init__(
        self,
        asset_repo: AssetRepository,
        storage_repo: FileStorageRepository | None = None,
    ):
        self.asset_repo = asset_repo
        self.storage_repo = storage_repo

    async def create(self, payload: SeniatAssetCreate) -> SeniatAsset:
        data = payload.model_dump()
        data["status"] = AssetStatus.IN_SEDE
        return await self.asset_repo.create(data)

    async def list(
        self,
        *,
        status: AssetStatus | None = None,
        q: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SeniatAsset]:
        return await self.asset_repo.list(status=status, q=q, skip=skip, limit=limit)

    async def get(self, asset_id: UUID) -> SeniatAsset | None:
        return await self.asset_repo.get(asset_id)

    async def update(self, asset_id: UUID, payload: SeniatAssetUpdate) -> SeniatAsset | None:
        data = payload.model_dump(exclude_unset=True)
        data.pop("status", None)
        data.pop("assigned_user_id", None)
        data.pop("photo_object_key", None)
        return await self.asset_repo.update(asset_id, data)

    async def delete(self, asset_id: UUID) -> bool:
        asset = await self.asset_repo.get(asset_id)
        if asset is None:
            return False
        open_out = await self.asset_repo.get_open_out_movement(asset_id)
        if open_out is not None:
            raise AssetFlowError("No se puede eliminar un bien con movimiento abierto")
        return await self.asset_repo.delete(asset_id)

    async def assign(self, asset_id: UUID, payload: AssetAssignRequest) -> SeniatAsset | None:
        asset = await self.asset_repo.get(asset_id)
        if asset is None:
            return None
        now = datetime.now(UTC)
        previous = await self.asset_repo.get_active_assignment(asset_id)
        if previous is not None and previous.id is not None:
            await self.asset_repo.close_assignment(previous.id, released_at=now)
        await self.asset_repo.create_assignment(
            {
                "asset_id": asset_id,
                "user_id": payload.user_id,
                "workstation": payload.workstation,
                "assigned_at": now,
            }
        )
        update_data: dict[str, Any] = {
            "status": AssetStatus.ASSIGNED,
            "assigned_user_id": payload.user_id,
        }
        if payload.workstation is not None:
            update_data["workstation"] = payload.workstation
        return await self.asset_repo.update(asset_id, update_data)

    async def release(self, asset_id: UUID) -> SeniatAsset | None:
        asset = await self.asset_repo.get(asset_id)
        if asset is None:
            return None
        active = await self.asset_repo.get_active_assignment(asset_id)
        if active is None or active.id is None:
            raise AssetFlowError("No hay asignación activa")
        now = datetime.now(UTC)
        await self.asset_repo.close_assignment(active.id, released_at=now)
        open_out = await self.asset_repo.get_open_out_movement(asset_id)
        update_data: dict[str, Any] = {"assigned_user_id": None}
        if open_out is None:
            update_data["status"] = AssetStatus.IN_SEDE
        return await self.asset_repo.update(asset_id, update_data)

    async def record_movement(
        self, asset_id: UUID, payload: AssetMovementCreate
    ) -> AssetMovement | None:
        asset = await self.asset_repo.get(asset_id)
        if asset is None:
            return None
        now = datetime.now(UTC)
        if payload.direction == AssetMovementDirection.OUT:
            return await self._open_out(asset_id, payload, at=now)
        if payload.direction == AssetMovementDirection.IN:
            return await self._close_out(asset_id, at=now)
        raise AssetFlowError("Dirección de movimiento inválida")

    async def _open_out(
        self, asset_id: UUID, payload: AssetMovementCreate, *, at: datetime
    ) -> AssetMovement:
        open_out = await self.asset_repo.get_open_out_movement(asset_id)
        if open_out is not None:
            raise AssetFlowError("Ya existe un movimiento de salida abierto")
        movement = await self.asset_repo.create_movement(
            {
                "asset_id": asset_id,
                "carrier_user_id": payload.carrier_user_id,
                "visit_id": payload.visit_id,
                "direction": AssetMovementDirection.OUT,
                "status": AssetMovementStatus.OPEN,
                "notes": payload.notes,
                "opened_at": at,
            }
        )
        await self.asset_repo.update(asset_id, {"status": AssetStatus.IN_TRANSIT_OUT})
        return movement

    async def _close_out(self, asset_id: UUID, *, at: datetime) -> AssetMovement:
        open_out = await self.asset_repo.get_open_out_movement(asset_id)
        if open_out is None:
            raise AssetFlowError("No hay un movimiento de salida abierto")
        closed = await self.asset_repo.close_movement(open_out.id, closed_at=at)
        if closed is None:
            raise AssetFlowError("No se pudo cerrar el movimiento de salida")
        active = await self.asset_repo.get_active_assignment(asset_id)
        new_status = AssetStatus.ASSIGNED if active is not None else AssetStatus.IN_SEDE
        await self.asset_repo.update(asset_id, {"status": new_status})
        return closed

    async def list_open_out_alerts(
        self, *, visit_id: UUID | None = None
    ) -> list[AssetMovement]:
        return await self.asset_repo.list_open_out(visit_id=visit_id)

    async def upload_photo(
        self,
        asset_id: UUID,
        *,
        file_data: bytes,
        filename: str,
    ) -> SeniatAsset | None:
        asset = await self.asset_repo.get(asset_id)
        if asset is None:
            return None
        if self.storage_repo is None:
            raise RuntimeError("Storage no configurado")
        if not file_data:
            raise ValueError("La imagen es obligatoria")
        if len(file_data) > _MAX_PHOTO_BYTES:
            raise ValueError("La imagen supera el limite de 10MB")
        sniffed = sniff_image_content_type(file_data)
        safe_name = Path(filename).name or "photo"
        object_key = f"{_PHOTO_PREFIX}/{asset_id}/{uuid4()}_{safe_name}"
        previous_key = asset.photo_object_key
        returned_key = await self.storage_repo.upload(
            file_data=file_data,
            key=object_key,
            content_type=sniffed,
        )
        try:
            updated = await self.asset_repo.update(
                asset_id, {"photo_object_key": returned_key}
            )
        except Exception:
            await self.storage_repo.delete(object_key)
            raise
        if previous_key:
            await self.storage_repo.delete(previous_key)
        return updated

    async def export_csv(self) -> str:
        assets = await self.asset_repo.list(skip=0, limit=_EXPORT_LIMIT)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "code",
                "serial",
                "brand",
                "model",
                "category",
                "status",
                "assigned_user_id",
                "workstation",
            ]
        )
        for asset in assets:
            status = (
                asset.status.value if isinstance(asset.status, AssetStatus) else str(asset.status)
            )
            writer.writerow(
                [
                    asset.inventory_code,
                    asset.serial or "",
                    asset.brand or "",
                    asset.model or "",
                    asset.category,
                    status,
                    str(asset.assigned_user_id) if asset.assigned_user_id else "",
                    asset.workstation or "",
                ]
            )
        return buffer.getvalue()
