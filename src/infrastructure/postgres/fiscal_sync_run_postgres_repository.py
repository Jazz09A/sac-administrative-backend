from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.domain.repositories.fiscal_sync_run_repository import FiscalSyncRunRepository
from src.models.fiscal import FiscalSyncRun, FiscalSyncRunStatus


class PostgresFiscalSyncRunRepository(FiscalSyncRunRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def start_run(self) -> FiscalSyncRun:
        run = FiscalSyncRun(status=FiscalSyncRunStatus.SUCCESS)
        self.session.add(run)
        await self.session.flush()
        return run

    async def finish_run(
        self,
        run: FiscalSyncRun,
        *,
        status: str,
        fetched_total: int,
        inserted_total: int,
        updated_total: int,
        skipped_total: int,
        error_message: str | None = None,
    ) -> FiscalSyncRun:
        run.status = FiscalSyncRunStatus(status)
        run.finished_at = datetime.utcnow()
        run.fetched_total = fetched_total
        run.inserted_total = inserted_total
        run.updated_total = updated_total
        run.skipped_total = skipped_total
        run.error_message = error_message
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_last_run(self) -> FiscalSyncRun | None:
        result = await self.session.execute(
            select(FiscalSyncRun).order_by(FiscalSyncRun.started_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()
