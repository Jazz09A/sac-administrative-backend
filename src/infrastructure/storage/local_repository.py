from pathlib import Path


class LocalFileStorageRepository:
    """Persist files on the local disk for on-premise LAN deployments."""

    def __init__(self, base_path: str | Path, public_base_url: str = "/api/v1/files") -> None:
        self.base_path = Path(base_path).resolve()
        self.public_base_url = public_base_url.rstrip("/")

    def _resolve_key(self, key: str) -> Path:
        relative = Path(key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Clave de almacenamiento invalida")
        destination = (self.base_path / relative).resolve()
        try:
            destination.relative_to(self.base_path)
        except ValueError as exc:
            raise ValueError("Clave de almacenamiento invalida") from exc
        return destination

    async def upload(self, file_data: bytes, key: str, content_type: str) -> str:
        del content_type
        destination = self._resolve_key(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(file_data)
        return key

    async def delete(self, key: str) -> bool:
        destination = self._resolve_key(key)
        if destination.is_file():
            destination.unlink()
        return True

    def get_public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{key.lstrip('/')}"
