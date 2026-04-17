from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.repositories.fiscal_source_repository import (
    ExternalFiscalRecord,
    FiscalSourceRepository,
)


class MySQLFiscalSourceRepository(FiscalSourceRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active_fiscals(self) -> list[ExternalFiscalRecord]:
        statement = text(
            """
            SELECT
                `id` AS external_id,
                `name`,
                `personId` AS person_id,
                `email`,
                `groupId` AS group_id,
                `supervisor_id` AS supervisor_id,
                `status`
            FROM `user`
            WHERE `role` = 'FISCAL' AND `status` = 1
            """
        )
        result = await self.session.execute(statement)
        fiscals: list[ExternalFiscalRecord] = []
        for row in result.mappings().all():
            fiscals.append(
                ExternalFiscalRecord(
                    external_id=str(row["external_id"]),
                    name=row["name"],
                    person_id=row["person_id"],
                    email=row["email"],
                    group_id=row["group_id"],
                    supervisor_id=row["supervisor_id"],
                    status=bool(row["status"]),
                )
            )
        return fiscals
