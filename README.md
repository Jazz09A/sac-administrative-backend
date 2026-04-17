# Sistema Contribuyentes Backend (MVP)

**Fecha última mod:** 2026-04-17 | **Cambios:** Init estructura, uv setup. Módulos: pyproject.toml, src/core/config.py.

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