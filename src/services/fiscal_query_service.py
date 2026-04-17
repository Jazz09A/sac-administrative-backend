from src.domain.repositories.fiscal_repository import FiscalRepository
from src.domain.repositories.fiscal_sync_run_repository import FiscalSyncRunRepository
from src.models.fiscal import Fiscal, FiscalSyncRun


class FiscalQueryService:
    def __init__(
        self,
        fiscal_repo: FiscalRepository,
        sync_run_repo: FiscalSyncRunRepository,
    ):
        self.fiscal_repo = fiscal_repo
        self.sync_run_repo = sync_run_repo

    async def search(self, query: str | None = None, limit: int = 100) -> list[Fiscal]:
        return await self.fiscal_repo.search(query=query, limit=limit)

    async def get_sync_status(self) -> FiscalSyncRun | None:
        return await self.sync_run_repo.get_last_run()
