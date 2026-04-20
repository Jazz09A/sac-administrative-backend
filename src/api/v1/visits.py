"""
API Visits: ingreso/salida MVP.
Última mod: 2026-04-17 09:03 | Changes: POST/PATCH con filtros.
"""
from datetime import date, time
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.database import get_db
from src.infrastructure.postgres.contributor_postgres_repository import PostgresContributorRepository
from src.infrastructure.postgres.fiscal_postgres_repository import PostgresFiscalRepository
from src.infrastructure.postgres.photo_postgres_repository import PostgresPhotoRepository
from src.infrastructure.postgres.visit_postgres_repository import PostgresVisitRepository
from src.infrastructure.storage.s3_repository import S3FileStorageRepository
from src.models.photo import PhotoPublic
from src.models.visit import (
    VisitCreate,
    VisitHistoryItem,
    VisitPublic,
    VisitStatus,
    VisitUpdateExit,
    VisitWithPhotosPublic,
)
from src.services.photo_service import PhotoService
from src.services.visit_service import VisitService

router = APIRouter()

@router.post("/", response_model=VisitWithPhotosPublic, status_code=status.HTTP_201_CREATED)
async def register_ingreso(
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

    bucket_name = settings.BUCKET_NAME_S3.strip()
    if not bucket_name:
        raise HTTPException(
            status_code=500,
            detail="Configuracion incompleta: BUCKET_NAME_S3 es obligatorio",
        )

    visit_in = VisitCreate(
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
    photo_service = PhotoService(
        photo_repo=PostgresPhotoRepository(db),
        storage_repo=S3FileStorageRepository(
            endpoint_url=settings.URL_BUCKET_S3,
            access_key_id=settings.ACCESS_KEY_S3,
            secret_access_key=settings.SECRET_ACCESS_KEY_S3,
            bucket_name=bucket_name,
            region_name=settings.S3_REGION,
        ),
    )

    public_base_url = settings.R2_PUBLIC_BASE_URL.rstrip("/")

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
        photo_url = (
            f"{public_base_url}/{created_photo.object_key}" if public_base_url else created_photo.object_key
        )
        visit.signature_image_url = photo_url
        db.add(visit)
        await db.flush()
        await db.refresh(visit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await photo.close()

    photo_public = PhotoPublic.model_validate(created_photo)
    photo_public.photo_url = photo_url

    return VisitWithPhotosPublic.model_validate(
        visit,
        update={"photos": [photo_public]},
    )

@router.get("/", response_model=List[VisitPublic])
async def list_visits(
    contributor_id: int | None = None,
    rif: str | None = None,
    status: str | None = None,
    fiscal_id: int | None = None,
    entry_date: date | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
) -> List[VisitPublic]:
    """Búsqueda historial."""
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
    return [
        VisitPublic.model_validate(
            visit,
            update={"fiscal_name": visit.fiscal.name if visit.fiscal else None},
        )
        for visit in visits
    ]

@router.get("/history", response_model=List[VisitHistoryItem])
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
) -> List[VisitHistoryItem]:
    """Historial con columnas para reporte administrativo. Muestra todas las visitas por defecto."""
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
    return [VisitHistoryItem.model_validate(row) for row in rows]

@router.get("/{visit_id}", response_model=VisitPublic)
async def get_visit_detail(
    visit_id: UUID, db: AsyncSession = Depends(get_db)
) -> VisitPublic:
    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    visit = await service.get(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visita no encontrada")
    return VisitPublic.model_validate(
        visit,
        update={"fiscal_name": visit.fiscal.name if visit.fiscal else None},
    )

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
    return VisitPublic.model_validate(
        visit,
        update={"fiscal_name": visit.fiscal.name if visit.fiscal else None},
    )

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
    return VisitPublic.model_validate(
        visit,
        update={"fiscal_name": visit.fiscal.name if visit.fiscal else None},
    )