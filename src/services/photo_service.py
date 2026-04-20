from pathlib import Path
from uuid import UUID, uuid4

from src.domain.repositories.file_storage_repository import FileStorageRepository
from src.domain.repositories.photo_repository import PhotoRepository
from src.models.photo import Photo


class PhotoService:
    OBJECT_PREFIX = "sac-administrative/sac-visits"
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
    ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

    def __init__(
        self,
        photo_repo: PhotoRepository,
        storage_repo: FileStorageRepository,
    ):
        self.photo_repo = photo_repo
        self.storage_repo = storage_repo

    async def upload_visit_photo(
        self,
        *,
        visit_id: UUID,
        file_data: bytes,
        filename: str,
        content_type: str,
    ) -> Photo:
        self._validate_file(file_data=file_data, content_type=content_type)

        safe_name = Path(filename).name or "photo"
        object_key = f"{self.OBJECT_PREFIX}/{visit_id}/{uuid4()}_{safe_name}"
        object_url = await self.storage_repo.upload(
            file_data=file_data,
            key=object_key,
            content_type=content_type,
        )
        try:
            return await self.photo_repo.create(visit_id=visit_id, photo_url=object_url)
        except Exception:
            await self.storage_repo.delete(object_key)
            raise

    async def list_visit_photos(self, visit_id: UUID) -> list[Photo]:
        return await self.photo_repo.list_by_visit(visit_id)

    def _validate_file(self, *, file_data: bytes, content_type: str) -> None:
        if not file_data:
            raise ValueError("La imagen es obligatoria")
        if len(file_data) > self.MAX_FILE_SIZE_BYTES:
            raise ValueError("La imagen supera el limite de 10MB")
        if content_type not in self.ALLOWED_CONTENT_TYPES:
            raise ValueError("Formato no permitido. Use JPG, PNG o WEBP")
