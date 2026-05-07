"""
API Visits: ingreso/salida MVP.
Última mod: 2026-04-17 09:03 | Changes: POST/PATCH con filtros.
"""
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.config import Settings, get_settings
from src.core.database import get_db
from src.infrastructure.postgres.contributor_postgres_repository import (
    PostgresContributorRepository,
)
from src.infrastructure.postgres.fiscal_postgres_repository import PostgresFiscalRepository
from src.infrastructure.postgres.photo_postgres_repository import PostgresPhotoRepository
from src.infrastructure.postgres.visit_postgres_repository import PostgresVisitRepository
from src.infrastructure.storage.storage_factory import create_file_storage_repository
from src.models.contributor import Contributor
from src.models.fiscal import Fiscal
from src.models.photo import PhotoPublic
from src.models.visit import (
    FiscalVisitReportItem,
    FiscalVisitsReportResponse,
    Visit,
    VisitCreate,
    VisitHistoryItem,
    VisitHistoryReportResponse,
    VisitPublic,
    VisitStatus,
    VisitUpdate,
    VisitUpdateExit,
    VisitWithPhotosPublic,
)
from src.realtime.visit_ws_manager import visit_ws_manager
from src.services.photo_service import PhotoService
from src.services.visit_service import VisitService

router = APIRouter()

try:
    VENEZUELA_TZ = ZoneInfo("America/Caracas")
except ZoneInfoNotFoundError:
    # Windows envs without tzdata should not crash app startup.
    VENEZUELA_TZ = timezone(timedelta(hours=-4))


def _venezuela_today() -> date:
    return datetime.now(VENEZUELA_TZ).date()


def _visit_names_update(visit: Visit) -> dict[str, str | None]:
    return {
        "fiscal_name": visit.fiscal.name if visit.fiscal else None,
        "contributor_name": visit.contributor.name if visit.contributor else None,
    }


async def _build_visit_with_photos(
    *,
    visit: Visit,
    photo_service: PhotoService,
) -> VisitWithPhotosPublic:
    photos = await photo_service.list_visit_photos(visit.id)
    photo_public = [
        PhotoPublic.model_validate(
            photo,
            update={"photo_url": photo_service.storage_repo.get_public_url(photo.object_key)},
        )
        for photo in photos
    ]
    return VisitWithPhotosPublic.model_validate(
        visit,
        update={
            **_visit_names_update(visit),
            "photos": photo_public,
        },
    )


@router.get("/reports/fiscals", response_model=FiscalVisitsReportResponse)
async def fiscal_visits_report(
    fiscal_id: int | None = None,
    status_filter: str | None = None,
    contributor_name: str | None = None,
    rif: str | None = None,
    fiscal_status: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> FiscalVisitsReportResponse:
    if date_from is None and date_to is None:
        today_ve = _venezuela_today()
        date_from = today_ve
        date_to = today_ve

    base_statement = (
        select(Visit, Contributor, Fiscal)
        .join(Contributor, Visit.contributor_id == Contributor.id)
        .join(Fiscal, Visit.fiscal_id == Fiscal.id, isouter=True)
        .where(Visit.deleted_at.is_(None))
    )

    if fiscal_id:
        base_statement = base_statement.where(Visit.fiscal_id == fiscal_id)
    if status_filter:
        status_values = [s.strip() for s in status_filter.split(",") if s.strip()]
        if len(status_values) == 1:
            base_statement = base_statement.where(Visit.status == status_values[0])
        elif status_values:
            base_statement = base_statement.where(Visit.status.in_(status_values))
    if contributor_name:
        base_statement = base_statement.where(
            Contributor.name.ilike(f"%{contributor_name.strip()}%")
        )
    if rif:
        base_statement = base_statement.where(Contributor.rif.ilike(f"%{rif.strip()}%"))
    if fiscal_status is not None:
        base_statement = base_statement.where(Fiscal.status == fiscal_status)
    if date_from:
        base_statement = base_statement.where(Visit.entry_date >= date_from)
    if date_to:
        base_statement = base_statement.where(Visit.entry_date <= date_to)
    if q:
        term = f"%{q.strip()}%"
        base_statement = base_statement.where(
            Contributor.name.ilike(term) | Contributor.rif.ilike(term)
        )

    try:
        total_statement = select(func.count()).select_from(base_statement.subquery())
        total = int((await db.execute(total_statement)).scalar_one())
        statement = base_statement.order_by(Visit.created_at.desc()).offset(skip).limit(limit)
        rows = (await db.execute(statement)).all()
    except (SQLAlchemyError, Exception) as exc:
        raise HTTPException(
            status_code=503,
            detail="Base de datos no disponible para generar el reporte por fiscal.",
        ) from exc
    items = [
        FiscalVisitReportItem(
            visit_id=visit.id,
            fiscal_id=visit.fiscal_id,
            fiscal_name=fiscal.name if fiscal else None,
            contributor_id=contributor.id or 0,
            contributor_name=contributor.name,
            contributor_rif=contributor.rif,
            entry_date=visit.entry_date,
            entry_time=visit.entry_time,
            exit_date=visit.exit_date,
            exit_time=visit.exit_time,
            status=visit.status,
            reason=visit.reason,
            department=visit.department,
        )
        for visit, contributor, fiscal in rows
    ]
    return FiscalVisitsReportResponse(total=total, skip=skip, limit=limit, items=items)

@router.post("/", response_model=VisitWithPhotosPublic, status_code=status.HTTP_201_CREATED)
async def register_ingreso(
    contributor_rif: str = Form(...),
    contributor_name: str = Form(...),
    fiscal_id: str = Form(...),
    responsible_person: str = Form(...),
    reason: str = Form(...),
    observations: str | None = Form(None),
    department: str | None = Form(None),
    file_number: str | None = Form(None),
    entry_date: date = Form(...),
    entry_time: time = Form(...),
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VisitWithPhotosPublic:
    """Registro nuevo ingreso (imagen obligatoria)."""
    if not photo.filename:
        raise HTTPException(status_code=400, detail="La imagen es obligatoria")

    if settings.STORAGE_PROVIDER == "supabase":
        bucket_name = settings.BUCKET_NAME_SUPABASE.strip()
        bucket_name_setting_name = "BUCKET_NAME_SUPABASE"
    else:
        bucket_name = settings.BUCKET_NAME_S3.strip()
        bucket_name_setting_name = "BUCKET_NAME_S3"
    if not bucket_name:
        raise HTTPException(
            status_code=500,
            detail=f"Configuracion incompleta: {bucket_name_setting_name} es obligatorio",
        )

    visit_in = VisitCreate(
        contributor_rif=contributor_rif,
        contributor_name=contributor_name,
        fiscal_id=fiscal_id,
        responsible_person=responsible_person,
        reason=reason,
        observations=observations,
        department=department,
        file_number=file_number,
        entry_date=entry_date,
        entry_time=entry_time,
    )

    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    storage_repo = create_file_storage_repository(settings)
    photo_service = PhotoService(
        photo_repo=PostgresPhotoRepository(db),
        storage_repo=storage_repo,
    )

    try:
        visit = await service.create(visit_in)
        file_data = await photo.read()
        created_photo = await photo_service.upload_visit_photo(
            visit_id=visit.id,
            file_data=file_data,
            filename=photo.filename,
            content_type=photo.content_type or "",
            bucket_name=bucket_name,
        )
        photo_url = storage_repo.get_public_url(created_photo.object_key)
        visit.signature_image_url = photo_url
        db.add(visit)
        await db.flush()
        # Recargar con relaciones para evitar MissingGreenlet al serializar
        refreshed_visit = await service.get(visit.id)
        if not refreshed_visit:
            raise HTTPException(status_code=404, detail="Visita no encontrada tras actualizar firma")
        visit = refreshed_visit
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await photo.close()

    photo_public = PhotoPublic.model_validate(created_photo)
    photo_public.photo_url = photo_url

    response = VisitWithPhotosPublic.model_validate(
        visit,
        update={
            **_visit_names_update(visit),
            "photos": [photo_public],
        },
    )
    await visit_ws_manager.publish("visit.created", response)
    return response

@router.get("/", response_model=list[VisitPublic | VisitWithPhotosPublic])
async def list_visits(
    contributor_id: int | None = None,
    rif: str | None = None,
    status: str | None = None,
    fiscal_id: int | None = None,
    entry_date: date | None = None,
    include_images: bool = Query(
        default=False,
        description="Incluye arreglo photos con photo_url por visita.",
    ),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[VisitPublic | VisitWithPhotosPublic]:
    """B?squeda historial."""
    if entry_date is None:
        entry_date = _venezuela_today()

    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    visits = await service.list(
        contributor_id=contributor_id,
        rif=rif,
        status=status,
        fiscal_id=fiscal_id,
        entry_date=entry_date,
        skip=skip,
        limit=limit,
    )
    visits_public = [
        VisitPublic.model_validate(
            visit,
            update=_visit_names_update(visit),
        )
        for visit in visits
    ]
    if not include_images:
        return visits_public

    storage_repo = create_file_storage_repository(settings)
    photo_service = PhotoService(
        photo_repo=PostgresPhotoRepository(db),
        storage_repo=storage_repo,
    )
    return [
        await _build_visit_with_photos(visit=visit, photo_service=photo_service)
        for visit in visits
    ]

@router.get("/history", response_model=VisitHistoryReportResponse)
async def list_visit_history(
    rif: str | None = None,
    contribuyente: str | None = None,
    registro: str | None = None,
    departamento: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    incluir_finalizados: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
) -> VisitHistoryReportResponse:
    """Historial con columnas para reporte administrativo. Muestra todas las visitas por defecto."""
    if fecha_desde is None and fecha_hasta is None:
        today_ve = _venezuela_today()
        fecha_desde = today_ve
        fecha_hasta = today_ve

    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    rows = await service.history(
        rif=rif,
        contributor_name=contribuyente,
        file_number=registro,
        department=departamento,
        date_from=fecha_desde,
        date_to=fecha_hasta,
        status_list=None if incluir_finalizados else [VisitStatus.ESPERA, VisitStatus.ATENDIDO],
        skip=skip,
        limit=limit,
    )
    total = await service.history_count(
        rif=rif,
        contributor_name=contribuyente,
        file_number=registro,
        department=departamento,
        date_from=fecha_desde,
        date_to=fecha_hasta,
        status_list=None if incluir_finalizados else [VisitStatus.ESPERA, VisitStatus.ATENDIDO],
    )
    items = [VisitHistoryItem.model_validate(row) for row in rows]
    return VisitHistoryReportResponse(total=total, skip=skip, limit=limit, items=items)

@router.get("/{visit_id}", response_model=VisitPublic | VisitWithPhotosPublic)
async def get_visit_detail(
    visit_id: UUID,
    include_images: bool = Query(
        default=False,
        description="Incluye arreglo photos con photo_url.",
    ),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VisitPublic | VisitWithPhotosPublic:
    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    visit = await service.get(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visita no encontrada")
    if not include_images:
        return VisitPublic.model_validate(
            visit,
            update=_visit_names_update(visit),
        )

    storage_repo = create_file_storage_repository(settings)
    photo_service = PhotoService(
        photo_repo=PostgresPhotoRepository(db),
        storage_repo=storage_repo,
    )
    return await _build_visit_with_photos(visit=visit, photo_service=photo_service)

@router.patch("/{visit_id}/attend", response_model=VisitPublic)
async def mark_visit_attended(
    visit_id: UUID, db: AsyncSession = Depends(get_db)
) -> VisitPublic:
    """Marca la visita como atendida (solo si esta en espera)."""
    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    visit = await service.mark_as_attended(visit_id)
    if not visit:
        raise HTTPException(status_code=400, detail="No se puede marcar como atendido. La visita debe estar en espera.")
    response = VisitPublic.model_validate(
        visit,
        update=_visit_names_update(visit),
    )
    await visit_ws_manager.publish("visit.attended", response)
    return response


@router.patch("/{visit_id}", response_model=VisitPublic)
async def update_visit(
    visit_id: UUID, visit_data: VisitUpdate, db: AsyncSession = Depends(get_db)
) -> VisitPublic:
    """Corrige campos editables de una visita."""
    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    try:
        visit = await service.update(visit_id, visit_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not visit:
        raise HTTPException(status_code=404, detail="Visita no encontrada")
    response = VisitPublic.model_validate(
        visit,
        update=_visit_names_update(visit),
    )
    await visit_ws_manager.publish("visit.updated", response)
    return response

@router.patch("/{visit_id}/exit", response_model=VisitPublic)
async def register_salida(
    visit_id: UUID, exit_data: VisitUpdateExit, db: AsyncSession = Depends(get_db)
) -> VisitPublic:
    """Actualiza salida (solo si espera)."""
    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    visit = await service.register_exit(visit_id, exit_data)
    if not visit:
        raise HTTPException(status_code=400, detail="No se puede registrar salida")
    response = VisitPublic.model_validate(
        visit,
        update=_visit_names_update(visit),
    )
    await visit_ws_manager.publish("visit.exited", response)
    return response


@router.delete("/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visit(
    visit_id: UUID, db: AsyncSession = Depends(get_db)
) -> None:
    """Borrado logico de visita (soft delete)."""
    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    visit = await service.soft_delete(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visita no encontrada")
    await visit_ws_manager.publish("visit.deleted", {"id": str(visit_id)})