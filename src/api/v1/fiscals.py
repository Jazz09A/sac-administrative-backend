from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.mysql_database import get_mysql_db
from src.infrastructure.mysql.fiscal_source_mysql_repository import MySQLFiscalSourceRepository
from src.infrastructure.postgres.fiscal_postgres_repository import PostgresFiscalRepository
from src.infrastructure.postgres.fiscal_sync_run_postgres_repository import (
    PostgresFiscalSyncRunRepository,
)
from src.models.fiscal import FiscalPublic, FiscalSyncRunPublic, FiscalSyncSummaryPublic
from src.services.fiscal_query_service import FiscalQueryService
from src.services.fiscal_sync_service import FiscalSyncService

router = APIRouter()


@router.get("/", response_model=list[FiscalPublic])
async def search_fiscals(
    query: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[FiscalPublic]:
    fiscal_repo = PostgresFiscalRepository(db)
    sync_run_repo = PostgresFiscalSyncRunRepository(db)
    service = FiscalQueryService(fiscal_repo, sync_run_repo)
    fiscals = await service.search(query=query, skip=skip, limit=limit)
    return [FiscalPublic.model_validate(fiscal) for fiscal in fiscals]


@router.get("/{fiscal_id}", response_model=FiscalPublic)
async def get_fiscal_by_id(
    fiscal_id: int,
    db: AsyncSession = Depends(get_db),
) -> FiscalPublic:
    fiscal_repo = PostgresFiscalRepository(db)
    fiscal = await fiscal_repo.get_by_id(fiscal_id)
    if not fiscal:
        raise HTTPException(status_code=404, detail="Fiscal no encontrado")
    return FiscalPublic.model_validate(fiscal)

@router.post("/sync", response_model=FiscalSyncSummaryPublic, status_code=status.HTTP_200_OK)
async def sync_fiscals(
    db: AsyncSession = Depends(get_db),
    mysql_db: AsyncSession = Depends(get_mysql_db),
) -> FiscalSyncSummaryPublic:
    source_repo = MySQLFiscalSourceRepository(mysql_db)
    fiscal_repo = PostgresFiscalRepository(db)
    sync_run_repo = PostgresFiscalSyncRunRepository(db)
    service = FiscalSyncService(source_repo, fiscal_repo, sync_run_repo)

    summary = await service.sync()
    return FiscalSyncSummaryPublic.model_validate(summary.to_dict())


@router.get("/sync/status", response_model=FiscalSyncRunPublic)
async def sync_status(
    db: AsyncSession = Depends(get_db),
) -> FiscalSyncRunPublic:
    fiscal_repo = PostgresFiscalRepository(db)
    sync_run_repo = PostgresFiscalSyncRunRepository(db)
    service = FiscalQueryService(fiscal_repo, sync_run_repo)
    last_run = await service.get_sync_status()
    if not last_run:
        raise HTTPException(status_code=404, detail="No hay sincronizaciones registradas")
    return FiscalSyncRunPublic.model_validate(last_run)
