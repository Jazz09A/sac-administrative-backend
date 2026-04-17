# Contexto IA para Sistema Contribuyentes

**Última mod:** 2026-04-17 | **Cambios:** Init. Módulos: todos.

## Reglas Estrictas
- **uv only**: `uv add/rm/sync`. pyproject.toml [tool.uv] locked.
- **SOLID**: SRP (crud solo DB, api solo routes), DIP (interfaces via protocols).
- **Clases definidas**: SQLModel hereda BaseModel, Pydantic ResponseModels tipadas.
- **Modular**: src/api/v1/{entity}.py | crud/{entity}.py | models/{entity}.py.
- **Postgres**: AsyncSession, indexes en rif/date/status.
- **Responses**: Siempre ResponseModel.from_orm() o dict(tipo=List[EntityOut]).
- **Tests**: Unit (crud funcs), integration (TestClient endpoints). pytest.mark.asyncio. Auto-run: pre-commit.
- **Commits**: git diff -- tests si cambias código.

## Módulos (descripción corta)
- **src/main.py**: FastAPI app, routers include, CORS/DB deps.
- **src/core/config.py**: Settings (pydantic-settings), DATABASE_URL, SECRET_KEY.
- **src/core/security.py**: JWT utils (create/access_token).
- **src/models/**: SQLModel classes (Contributor, Visit, Photo). Relations 1:N.
- **src/crud/**: Async CRUD funcs (get_by_rif, create_visit). Usa DbSession.
- **src/api/v1/**: APIRouters. Deps: auth, CurrentUser. Responses tipadas.
- **tests/**: conftest.py (TestClient, override_db), test_crud_*.py, test_api_*.py.
- **alembic/**: Autogenerate migrations: `uv run alembic revision --autogenerate`.

## MVP Endpoints (de propuesta)
- POST /contributors, GET /contributors/?rif=, /:id
- POST /visits (ingreso+foto), PATCH /visits/:id/exit, GET /visits/?status=
- GET /dashboard/summary (hoy: totales, en_espera)

Genera código: "crea crud/contributor.py con get_or_create_by_rif".