from typing import Protocol


class FileStorageRepository(Protocol):
    async def upload(self, file_data: bytes, key: str, content_type: str) -> str:
        """Upload file bytes and return the object key (not the full URL)."""

    async def delete(self, key: str) -> bool:
        """Delete object by key."""

    def get_public_url(self, key: str) -> str:
        """Build a public URL for the object key using provider strategy."""
