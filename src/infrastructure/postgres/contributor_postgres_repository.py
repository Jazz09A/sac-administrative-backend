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

    async def get_or_create_by_rif(self, rif: str, name: str) -> Contributor:
        normalized_rif = rif.strip()
        existing = await self.get_by_rif(normalized_rif)
        if existing:
            return existing
        contributor = Contributor(
            rif=normalized_rif,
            name=name.strip(),
            type=ContributorType.NATURAL,
            occupation=None,
            phone=None,
            email=None,
        )
        self.session.add(contributor)
        await self.session.flush()
        await self.session.refresh(contributor)
        return contributor
