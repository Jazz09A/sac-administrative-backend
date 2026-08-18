import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("MYSQL_DATABASE_URL", "mysql+asyncmy://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "k" * 32)
os.environ.setdefault("AUTH_PERSON_ID", "V12345678")
os.environ.setdefault("AUTH_PASSWORD", "password1")
os.environ.setdefault("ADMIN_EMAIL", "admin@local")

from src.core.security import CurrentUser, require_roles


@pytest.mark.asyncio
async def test_require_roles_allows_matching_role() -> None:
    checker = require_roles("gate", "admin")
    user = CurrentUser(person_id="V123", role="gate")
    assert await checker(user) == user


@pytest.mark.asyncio
async def test_require_roles_rejects_other_role() -> None:
    checker = require_roles("admin")
    with pytest.raises(HTTPException) as exc:
        await checker(CurrentUser(person_id="V123", role="user"))
    assert exc.value.status_code == 403
