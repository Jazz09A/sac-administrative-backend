from datetime import date
from typing import Any, List
from uuid import UUID

from src.domain.repositories.contributor_repository import ContributorRepository
from src.domain.repositories.fiscal_repository import FiscalRepository
from src.domain.repositories.visit_repository import VisitRepository
from src.models.visit import Visit, VisitCreate, VisitStatus, VisitUpdateExit


class VisitService:
    def __init__(
        self,
        contributor_repo: ContributorRepository,
        fiscal_repo: FiscalRepository,
        visit_repo: VisitRepository,
    ):
        self.contributor_repo = contributor_repo
        self.fiscal_repo = fiscal_repo
        self.visit_repo = visit_repo

    async def create(self, visit_in: VisitCreate) -> Visit:
        contributor = await self.contributor_repo.get_by_name(visit_in.contributor_name)
        if contributor is None:
            contributor = await self.contributor_repo.create_minimal(visit_in.contributor_name)

        fiscal = await self._resolve_fiscal(visit_in.fiscal_id)
        if fiscal is None:
            raise ValueError("Fiscal no existe")
        if not fiscal.status:
            raise ValueError("Fiscal inactivo")

        responsible_person = visit_in.responsible_person.strip()
        visit_data = {
            "contributor_id": contributor.id,
            "fiscal_id": fiscal.id,
            "reason": visit_in.reason,
            "observations": visit_in.observations,
            "received_by": responsible_person,
            "department": visit_in.department,
            "file_number": visit_in.file_number,
            "entry_date": visit_in.entry_date,
            "entry_time": visit_in.entry_time,
            "signature_image_url": visit_in.signature_image_url,
        }
        return await self.visit_repo.create(visit_data, responsible_snapshot=responsible_person)

    async def _resolve_fiscal(self, fiscal_identifier: str):
        value = fiscal_identifier.strip()
        if not value:
            raise ValueError("fiscal_id es obligatorio")

        # Accept local integer id or external UUID/id from source system.
        if value.isdigit():
            return await self.fiscal_repo.get_by_id(int(value))
        return await self.fiscal_repo.get_by_external_id(value)

    async def list(
        self,
        *,
        contributor_id: int | None = None,
        rif: str | None = None,
        status: str | None = None,
        fiscal_id: int | None = None,
        entry_date: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Visit]:
        return await self.visit_repo.list(
            contributor_id=contributor_id,
            rif=rif,
            status=status,
            fiscal_id=fiscal_id,
            entry_date=entry_date,
            skip=skip,
            limit=limit,
        )

    async def get(self, visit_id: UUID) -> Visit | None:
        return await self.visit_repo.get(visit_id)

    async def register_exit(self, visit_id: UUID, exit_data: VisitUpdateExit) -> Visit | None:
        return await self.visit_repo.register_exit(visit_id, exit_data)

    async def history(
        self,
        *,
        rif: str | None = None,
        contributor_name: str | None = None,
        file_number: str | None = None,
        department: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        status_list: List[VisitStatus] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[dict[str, Any]]:
        return await self.visit_repo.list_history(
            rif=rif,
            contributor_name=contributor_name,
            file_number=file_number,
            department=department,
            date_from=date_from,
            date_to=date_to,
            status_list=status_list,
            skip=skip,
            limit=limit,
        )
