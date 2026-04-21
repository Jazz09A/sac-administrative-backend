# Sistema Contribuyentes Backend (MVP)

**Fecha última mod:** 2026-04-21 | **Cambios:** Agregado campo `role` en tabla `users` (valores: `admin`, `user`) y endpoint `GET /api/v1/auth/me`. Migration: `4457b74aa740_add_users_table_with_role.py`. Módulos: `src/models/user.py`, `alembic/env.py`, `src/api/v1/auth.py`.

## Stack & Prácticas
- **FastAPI + SQLModel** (modular, SOLID: SRP en crud/api).
- **uv** (pip rápido): `uv sync` para deps/lock.
- **Postgres** via Alembic migrations.
- **Tests**: pytest unit/integration, auto-run en pre-commit.
- **Arquitectura**: Hexagonal-like (models -> crud -> api), Pydantic responses.

## Setup Local
```bash
uv sync
cp .env.example .env  # DATABASE_URL=postgresql://user:pass@localhost/db
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
```

## Tests
```bash
uv run pytest  # Unit + integration
```

## Estructura
Ver [CLAUDE.md].