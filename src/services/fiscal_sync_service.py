from dataclasses import asdict, dataclass
from datetime import datetime

from src.domain.repositories.fiscal_repository import FiscalRepository
from src.domain.repositories.fiscal_source_repository import FiscalSourceRepository
from src.domain.repositories.fiscal_sync_run_repository import FiscalSyncRunRepository


@dataclass
class FiscalSyncSummary:
    started_at: datetime
    finished_at: datetime
    fetched_total: int
    inserted_total: int
    updated_total: int
    skipped_total: int
    duration_ms: int
    status: str
    error_message: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["finished_at"] = self.finished_at.isoformat()
        return data


class FiscalSyncService:
    def __init__(
        self,
        source_repo: FiscalSourceRepository,
        fiscal_repo: FiscalRepository,
        sync_run_repo: FiscalSyncRunRepository,
    ):
        self.source_repo = source_repo
        self.fiscal_repo = fiscal_repo
        self.sync_run_repo = sync_run_repo

    async def sync(self) -> FiscalSyncSummary:
        started_at = datetime.utcnow()
        run = await self.sync_run_repo.start_run()

        try:
            external_rows = await self.source_repo.list_active_fiscals()
            payload = [
                {
                    "external_id": row.external_id,
                    "name": row.name,
                    "person_id": row.person_id,
                    "email": row.email,
                    "group_id": row.group_id,
                    "supervisor_id": row.supervisor_id,
                    "status": row.status,
                }
                for row in external_rows
            ]

            inserted_total, updated_total = await self.fiscal_repo.upsert_many(payload)
            fetched_total = len(payload)
            skipped_total = max(fetched_total - (inserted_total + updated_total), 0)
            finished_at = datetime.utcnow()
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)

            await self.sync_run_repo.finish_run(
                run,
                status="success",
                fetched_total=fetched_total,
                inserted_total=inserted_total,
                updated_total=updated_total,
                skipped_total=skipped_total,
            )

            return FiscalSyncSummary(
                started_at=started_at,
                finished_at=finished_at,
                fetched_total=fetched_total,
                inserted_total=inserted_total,
                updated_total=updated_total,
                skipped_total=skipped_total,
                duration_ms=duration_ms,
                status="success",
            )
        except Exception as exc:
            finished_at = datetime.utcnow()
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            await self.sync_run_repo.finish_run(
                run,
                status="failed",
                fetched_total=0,
                inserted_total=0,
                updated_total=0,
                skipped_total=0,
                error_message=str(exc),
            )
            return FiscalSyncSummary(
                started_at=started_at,
                finished_at=finished_at,
                fetched_total=0,
                inserted_total=0,
                updated_total=0,
                skipped_total=0,
                duration_ms=duration_ms,
                status="failed",
                error_message=str(exc),
            )
