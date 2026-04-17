"""
API Visits: ingreso/salida MVP.
Última mod: 2026-04-17 09:03 | Changes: POST/PATCH con filtros.
"""
from datetime import date
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.infrastructure.postgres.contributor_postgres_repository import PostgresContributorRepository
from src.infrastructure.postgres.fiscal_postgres_repository import PostgresFiscalRepository
from src.infrastructure.postgres.visit_postgres_repository import PostgresVisitRepository
from src.models.visit import VisitCreate, VisitPublic, VisitUpdateExit
from src.services.visit_service import VisitService

router = APIRouter()

@router.post("/", response_model=VisitPublic, status_code=status.HTTP_201_CREATED)
async def register_ingreso(
    visit_in: VisitCreate, db: AsyncSession = Depends(get_db)
) -> VisitPublic:
    """Registro nuevo ingreso."""
    service = VisitService(
        contributor_repo=PostgresContributorRepository(db),
        fiscal_repo=PostgresFiscalRepository(db),
        visit_repo=PostgresVisitRepository(db),
    )
    try:
        visit = await service.create(visit_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return VisitPublic.model_validate(visit)

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
    return [VisitPublic.model_validate(visit) for visit in visits]

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
    return VisitPublic.model_validate(visit)

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
    return VisitPublic.model_validate(visit)