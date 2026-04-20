from typing import Protocol


class FileStorageRepository(Protocol):
    async def upload(self, file_data: bytes, key: str, content_type: str) -> str:
        """Upload file bytes and return object URL."""

    async def delete(self, key: str) -> bool:
        """Delete object by key."""
