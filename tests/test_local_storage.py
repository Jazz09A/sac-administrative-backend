import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.core.config import Settings
from src.infrastructure.storage.local_repository import LocalFileStorageRepository
from src.infrastructure.storage.storage_factory import create_file_storage_repository


def _settings(**overrides: object) -> Settings:
    payload: dict[str, object] = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
        "MYSQL_DATABASE_URL": "mysql+asyncmy://u:p@localhost/db",
        "SECRET_KEY": "k" * 32,
        "AUTH_PERSON_ID": "V12345678",
        "AUTH_PASSWORD": "password1",
        "ADMIN_EMAIL": "admin@local",
        "STORAGE_PROVIDER": "local",
        "LOCAL_STORAGE_PATH": "/tmp/sac-storage",
    }
    payload.update(overrides)
    return Settings(**payload)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_local_storage_upload_read_delete(tmp_path: Path) -> None:
    repo = LocalFileStorageRepository(tmp_path, public_base_url="/api/v1/files")
    key = "sac-visits/abc/photo.jpg"

    returned = await repo.upload(b"jpeg-bytes", key, "image/jpeg")
    assert returned == key
    assert (tmp_path / key).read_bytes() == b"jpeg-bytes"
    assert repo.get_public_url(key) == "/api/v1/files/sac-visits/abc/photo.jpg"

    assert await repo.delete(key) is True
    assert not (tmp_path / key).exists()


@pytest.mark.asyncio
async def test_local_storage_rejects_path_traversal(tmp_path: Path) -> None:
    repo = LocalFileStorageRepository(tmp_path)
    with pytest.raises(ValueError, match="invalida"):
        await repo.upload(b"x", "../secret.txt", "image/jpeg")


def test_settings_accept_local_storage_without_s3() -> None:
    settings = _settings()
    repo = create_file_storage_repository(settings)
    assert isinstance(repo, LocalFileStorageRepository)


def test_settings_reject_unknown_provider() -> None:
    with pytest.raises(ValueError, match="STORAGE_PROVIDER"):
        _settings(STORAGE_PROVIDER="ftp")
