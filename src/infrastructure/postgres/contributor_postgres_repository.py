from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.domain.repositories.contributor_repository import ContributorRepository
from src.models.contributor import Contributor, ContributorType


class PostgresContributorRepository(ContributorRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, contributor_id: int) -> Contributor | None:
        result = await self.session.execute(select(Contributor).where(Contributor.id == contributor_id))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Contributor | None:
        result = await self.session.execute(
            select(Contributor).where(func.lower(Contributor.name) == name.strip().lower())
        )
        return result.scalar_one_or_none()

    async def get_by_rif(self, rif: str) -> Contributor | None:
        normalized = rif.strip()
        result = await self.session.execute(select(Contributor).where(Contributor.rif == normalized))
        return result.scalar_one_or_none()

    async def get_by_cedula(self, cedula: str) -> Contributor | None:
        normalized = cedula.strip()
        if not normalized:
            return None
        result = await self.session.execute(
            select(Contributor).where(Contributor.cedula == normalized)
        )
        return result.scalar_one_or_none()

    async def get_or_create_by_rif(self, rif: str, name: str) -> Contributor:
        normalized_rif = rif.strip()
        if normalized_rif.upper().startswith("TEMP-"):
            raise ValueError("RIF temporal no permitido en registro de visita")
        existing = await self.get_by_rif(normalized_rif)
        if existing:
            return existing
        contributor = Contributor(
            rif=normalized_rif,
            name=name.strip() if name else None,
            type=ContributorType.NATURAL,
            occupation=None,
            phone=None,
            email=None,
        )
        self.session.add(contributor)
        await self.session.flush()
        await self.session.refresh(contributor)
        return contributor

    async def get_or_create_by_cedula(
        self,
        cedula: str,
        *,
        name: str | None = None,
        rif: str | None = None,
    ) -> Contributor:
        normalized = cedula.strip()
        if not normalized:
            raise ValueError("Cédula es obligatoria")
        existing = await self.get_by_cedula(normalized)
        if existing:
            return existing
        normalized_rif = rif.strip() if rif else None
        if normalized_rif and normalized_rif.upper().startswith("TEMP-"):
            raise ValueError("RIF temporal no permitido en registro de visita")
        contributor = Contributor(
            cedula=normalized,
            rif=normalized_rif or None,
            name=name.strip() if name else None,
            type=ContributorType.NATURAL,
            occupation=None,
            phone=None,
            email=None,
        )
        self.session.add(contributor)
        await self.session.flush()
        await self.session.refresh(contributor)
        return contributor

    async def update(self, contributor_id: int, data: dict[str, Any]) -> Contributor | None:
        contributor = await self.get(contributor_id)
        if contributor is None:
            return None
        for field_name, value in data.items():
            setattr(contributor, field_name, value)
        self.session.add(contributor)
        await self.session.flush()
        await self.session.refresh(contributor)
        return contributor
