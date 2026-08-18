"""CRUD de plantillas faciales."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.contributor import Contributor
from src.models.face_template import FaceRegion, FaceTemplate


async def list_templates_with_contributors(
    session: AsyncSession,
) -> list[tuple[FaceTemplate, Contributor]]:
    result = await session.execute(
        select(FaceTemplate, Contributor).join(
            Contributor, FaceTemplate.contributor_id == Contributor.id
        )
    )
    return list(result.all())


async def create_template(
    session: AsyncSession,
    *,
    contributor_id: int,
    region: FaceRegion,
    glasses: bool,
    embedding: bytes,
    mesh_vector: bytes | None,
) -> FaceTemplate:
    row = FaceTemplate(
        contributor_id=contributor_id,
        region=region,
        glasses=glasses,
        embedding=embedding,
        mesh_vector=mesh_vector,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
