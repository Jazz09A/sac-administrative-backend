from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.database import get_db
from src.core.security import require_admin, require_operator
from src.infrastructure.postgres.asset_postgres_repository import PostgresAssetRepository
from src.infrastructure.storage.storage_factory import create_file_storage_repository
from src.models.asset import (
    AssetAssignRequest,
    AssetMovementCreate,
    AssetMovementPublic,
    AssetStatus,
    SeniatAssetCreate,
    SeniatAssetPublic,
    SeniatAssetUpdate,
)
from src.services.asset_service import AssetFlowError, AssetService

router = APIRouter(dependencies=[Depends(require_operator)])
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _service(db: AsyncSession, settings: Settings | None = None) -> AssetService:
    storage = create_file_storage_repository(settings) if settings is not None else None
    return AssetService(
        asset_repo=PostgresAssetRepository(db),
        storage_repo=storage,
    )


def _flow_http(exc: AssetFlowError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/alerts/open-out", response_model=list[AssetMovementPublic])
async def list_open_out_alerts(
    db: DbSession,
    visit_id: Annotated[UUID | None, Query()] = None,
) -> list[AssetMovementPublic]:
    service = _service(db)
    movements = await service.list_open_out_alerts(visit_id=visit_id)
    return [AssetMovementPublic.model_validate(item) for item in movements]


@router.get("/export.csv")
async def export_assets_csv(db: DbSession) -> Response:
    service = _service(db)
    content = await service.export_csv()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="seniat-assets.csv"'},
    )


@router.post("/", response_model=SeniatAssetPublic, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: SeniatAssetCreate,
    db: DbSession,
    _: object = Depends(require_admin),
) -> SeniatAssetPublic:
    service = _service(db)
    try:
        asset = await service.create(payload)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Código de inventario o serial duplicado",
        ) from exc
    return SeniatAssetPublic.model_validate(asset)


@router.get("/", response_model=list[SeniatAssetPublic])
async def list_assets(
    db: DbSession,
    status_filter: Annotated[AssetStatus | None, Query(alias="status")] = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[SeniatAssetPublic]:
    service = _service(db)
    assets = await service.list(status=status_filter, q=q, skip=skip, limit=limit)
    return [SeniatAssetPublic.model_validate(item) for item in assets]


@router.get("/{asset_id}", response_model=SeniatAssetPublic)
async def get_asset(asset_id: UUID, db: DbSession) -> SeniatAssetPublic:
    service = _service(db)
    asset = await service.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bien no encontrado")
    return SeniatAssetPublic.model_validate(asset)


@router.patch("/{asset_id}", response_model=SeniatAssetPublic)
async def update_asset(
    asset_id: UUID,
    payload: SeniatAssetUpdate,
    db: DbSession,
    _: object = Depends(require_admin),
) -> SeniatAssetPublic:
    service = _service(db)
    asset = await service.update(asset_id, payload)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bien no encontrado")
    return SeniatAssetPublic.model_validate(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_asset(
    asset_id: UUID,
    db: DbSession,
    _: object = Depends(require_admin),
) -> None:
    service = _service(db)
    try:
        deleted = await service.delete(asset_id)
    except AssetFlowError as exc:
        raise _flow_http(exc) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bien no encontrado")


@router.post("/{asset_id}/photo", response_model=SeniatAssetPublic)
async def upload_asset_photo(
    asset_id: UUID,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    photo: Annotated[UploadFile, File()],
) -> SeniatAssetPublic:
    service = _service(db, settings)
    file_data = await photo.read()
    try:
        asset = await service.upload_photo(
            asset_id,
            file_data=file_data,
            filename=photo.filename or "photo",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    finally:
        await photo.close()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bien no encontrado")
    return SeniatAssetPublic.model_validate(asset)


@router.post("/{asset_id}/assign", response_model=SeniatAssetPublic)
async def assign_asset(
    asset_id: UUID,
    payload: AssetAssignRequest,
    db: DbSession,
) -> SeniatAssetPublic:
    service = _service(db)
    asset = await service.assign(asset_id, payload)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bien no encontrado")
    return SeniatAssetPublic.model_validate(asset)


@router.post("/{asset_id}/release", response_model=SeniatAssetPublic)
async def release_asset(asset_id: UUID, db: DbSession) -> SeniatAssetPublic:
    service = _service(db)
    try:
        asset = await service.release(asset_id)
    except AssetFlowError as exc:
        raise _flow_http(exc) from exc
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bien no encontrado")
    return SeniatAssetPublic.model_validate(asset)


@router.post("/{asset_id}/movements", response_model=AssetMovementPublic)
async def record_asset_movement(
    asset_id: UUID,
    payload: AssetMovementCreate,
    db: DbSession,
) -> AssetMovementPublic:
    service = _service(db)
    try:
        movement = await service.record_movement(asset_id, payload)
    except AssetFlowError as exc:
        raise _flow_http(exc) from exc
    if movement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bien no encontrado")
    return AssetMovementPublic.model_validate(movement)
