import asyncio

from supabase import create_client, Client

from src.domain.repositories.file_storage_repository import FileStorageRepository


class SupabaseFileStorageRepository(FileStorageRepository):
    def __init__(
        self,
        *,
        supabase_url: str, 
        supabase_key: str,
        bucket_name: str,
    ):
        self.supabase_url = supabase_url.rstrip("/")
        self.bucket_name = bucket_name 
        self.client: Client = create_client(self.supabase_url, supabase_key)

    async def upload(self, file_data: bytes, key: str, content_type: str) -> str:
        """Upload file and return only the object key."""
        await asyncio.to_thread(
            self.client.storage.from_(self.bucket_name).upload,
            key,
            file_data,
            file_options={"content-type": content_type},
        )
        return key

    async def delete(self, key: str) -> bool:
        await asyncio.to_thread(
            self.client.storage.from_(self.bucket_name).remove,
            [key]
        )
        return True

    def get_public_url(self, key: str) -> str:
        # Para buckets públicos en Supabase Storage.
        return f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{key}"