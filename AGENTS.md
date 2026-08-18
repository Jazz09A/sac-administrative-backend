# Contexto IA — API administrativa SENIAT

**Última mod:** 2026-08-17 | Stack de producción: FastAPI + Postgres + storage local. UI de producto: `sac-access-control/` (Next), no el prototipo `app/`.

## Reglas

- **uv only**: `uv add/rm/sync`.
- Entrypoint: `main.py` (`uv run uvicorn main:app --reload`). No existe `src/main.py`.
- Schema: `init_db()` hace `create_all`. **No ALTER.** `alembic/` está gitignored: no asumir migraciones versionadas en git.
- Storage default: `STORAGE_PROVIDER=local`. No reintroducir S3/Supabase como requisito.
- JWT siempre en routers con `require_operator` / `require_admin`. `REQUIRE_AUTH` en config no se lee en Depends.
- Bienes = patrimonio institucional. Sin `contributor_id` en el bien.
- Taquilla nueva: `/call` + `/intake` + `/close`. Close exige nombre y motivo. No usar `/attend`.
- Alta de visita: contribuyente por **cédula**. `rif`/`name`/`reason` nullable; unique RIF permite NULL. `create_all` no ALTER.
- Tests: `uv run pytest`. No instalar deps ni commit sin pedido explícito.

## Módulos actuales

- `main.py`: FastAPI, CORS, `GET /health`, `include_router(..., prefix=/api/v1)`
- `src/api/v1/`: auth, users, contributors, fiscals, visits, biometrics, assets, dashboard, ws
- `src/services/`: visit, asset, photo, biometrics (LBPH)
- `src/infrastructure/storage/local_repository.py`: bloquea `..` y paths absolutos
- `src/models/`: contributor (`cedula` unique nullable), visit (ticket/called/closed/exit), face_templates, seniat_assets*

Contrato: `docs/api_documentation.md`. Arquitectura: `docs/architecture.md`.
