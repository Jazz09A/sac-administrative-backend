from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.domain.repositories.fiscal_repository import FiscalRepository
from src.models.fiscal import Fiscal


class PostgresFiscalRepository(FiscalRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_many(self, fiscals: list[dict]) -> tuple[int, int]:
        if not fiscals:
            return 0, 0

        external_ids = [f["external_id"] for f in fiscals]
        existing_result = await self.session.execute(
            select(Fiscal).where(Fiscal.external_id.in_(external_ids))
        )
        existing_rows = {row.external_id: row for row in existing_result.scalars().all()}

        inserted = 0
        updated = 0
        sync_time = datetime.utcnow()

        for fiscal_data in fiscals:
            existing = existing_rows.get(fiscal_data["external_id"])
            if existing:
                existing.name = fiscal_data["name"]
                existing.person_id = fiscal_data["person_id"]
                existing.email = fiscal_data["email"]
                existing.group_id = fiscal_data["group_id"]
                existing.supervisor_id = fiscal_data["supervisor_id"]
                existing.status = fiscal_data["status"]
                existing.last_synced_at = sync_time
                existing.updated_at = sync_time
                self.session.add(existing)
                updated += 1
            else:
                new_row = Fiscal(
                    external_id=fiscal_data["external_id"],
                    name=fiscal_data["name"],
                    person_id=fiscal_data["person_id"],
                    email=fiscal_data["email"],
                    group_id=fiscal_data["group_id"],
                    supervisor_id=fiscal_data["supervisor_id"],
                    status=fiscal_data["status"],
                    last_synced_at=sync_time,
                )
                self.session.add(new_row)
                inserted += 1

        await self.session.flush()
        return inserted, updated

    async def search(
        self,
        query: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Fiscal]:
        statement = select(Fiscal).where(Fiscal.status.is_(True))
        if query:
            like_query = f"%{query.strip()}%"
            statement = statement.where(
                or_(Fiscal.name.ilike(like_query), Fiscal.external_id.ilike(like_query))
            )
        statement = statement.order_by(Fiscal.name.asc()).offset(skip).limit(limit)

        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_by_id(self, fiscal_id: int) -> Fiscal | None:
        result = await self.session.execute(select(Fiscal).where(Fiscal.id == fiscal_id))
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> Fiscal | None:
        result = await self.session.execute(
            select(Fiscal).where(Fiscal.external_id == external_id.strip())
        )
        return result.scalar_one_or_none()
