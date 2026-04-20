from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.domain.repositories.photo_repository import PhotoRepository
from src.models.photo import Photo


class PostgresPhotoRepository(PhotoRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        visit_id: UUID,
        object_key: str,
        *,
        bucket: Optional[str] = None,
        content_type: Optional[str] = None,
        original_filename: Optional[str] = None,
        size: Optional[int] = None,
    ) -> Photo:
        db_photo = Photo(
            visit_id=visit_id,
            object_key=object_key,
            bucket=bucket,
            content_type=content_type,
            original_filename=original_filename,
            size=size,
        )
        self.session.add(db_photo)
        await self.session.flush()
        await self.session.refresh(db_photo)
        return db_photo

    async def list_by_visit(self, visit_id: UUID) -> list[Photo]:
        result = await self.session.execute(
            select(Photo).where(Photo.visit_id == visit_id).order_by(Photo.created_at.desc())
        )
        return list(result.scalars().all())
