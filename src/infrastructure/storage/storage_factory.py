from src.core.config import Settings
from src.domain.repositories.file_storage_repository import FileStorageRepository
from src.infrastructure.storage.local_repository import LocalFileStorageRepository
from src.infrastructure.storage.s3_repository import S3FileStorageRepository
from src.infrastructure.storage.supabase_repository import SupabaseFileStorageRepository


def create_file_storage_repository(settings: Settings) -> FileStorageRepository:
    provider = settings.STORAGE_PROVIDER.strip().lower()
    if provider == "local":
        return LocalFileStorageRepository(
            base_path=settings.LOCAL_STORAGE_PATH,
            public_base_url=settings.LOCAL_STORAGE_PUBLIC_URL,
        )
    if provider == "s3":
        return S3FileStorageRepository(
            endpoint_url=settings.URL_BUCKET_S3,
            access_key_id=settings.ACCESS_KEY_S3,
            secret_access_key=settings.SECRET_ACCESS_KEY_S3,
            bucket_name=settings.BUCKET_NAME_S3,
            public_base_url=settings.R2_PUBLIC_BASE_URL,
            region_name=settings.S3_REGION,
            session_token=settings.TOKEN_VALUE_S3 or None,
        )
    if provider == "supabase":
        return SupabaseFileStorageRepository(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_KEY,
            bucket_name=settings.BUCKET_NAME_SUPABASE,
        )
    raise ValueError(f"Unsupported storage provider: {settings.STORAGE_PROVIDER}")