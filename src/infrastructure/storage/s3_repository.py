import asyncio
from io import BytesIO

import boto3

from src.domain.repositories.file_storage_repository import FileStorageRepository


class S3FileStorageRepository(FileStorageRepository):
    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        public_base_url: str = "",
        region_name: str = "auto",
        session_token: str | None = None,
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.bucket_name = bucket_name
        self.public_base_url = public_base_url.rstrip("/")
        self.client = boto3.client(
            service_name="s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token or None,
            region_name=region_name,
        )

    async def upload(self, file_data: bytes, key: str, content_type: str) -> str:
        """Upload file and return only the object key."""
        await asyncio.to_thread(
            self.client.upload_fileobj,
            BytesIO(file_data),
            self.bucket_name,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return key

    async def delete(self, key: str) -> bool:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket_name, Key=key)
        return True

    def get_public_url(self, key: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url}/{key}"
        return key
