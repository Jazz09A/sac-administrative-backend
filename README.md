# Sistema Contribuyentes / SENIAT — API administrativa

API FastAPI de producción para control de acceso SENIAT (on-premise LAN). Un Postgres, JWT, storage **local por defecto**.

Contrato de endpoints: [`docs/api_documentation.md`](docs/api_documentation.md).  
Arquitectura y schema: [`docs/architecture.md`](docs/architecture.md).

## Stack

- Python 3.13, FastAPI, SQLModel, Postgres async (`asyncpg`), uv
- Storage: `STORAGE_PROVIDER=local` (default) escribe en `LOCAL_STORAGE_PATH=data/storage`. S3/Supabase son opcionales
- Biometría: OpenCV LBPH en proceso (sin ArcFace/GPU en esta iteración)

## Setup local

```bash
uv sync
cp .env.example .env
# DATABASE_URL=postgresql+asyncpg://...
uv run uvicorn main:app --reload
```

OpenAPI de FastAPI: `http://127.0.0.1:8000/docs` (generado en runtime; no hay spec estática versionada aquí).

El arranque llama `SQLModel.metadata.create_all`. **No altera tablas ya existentes.** El directorio `alembic/` está en `.gitignore`: no hay migraciones Alembic versionadas en git. En Postgres ya creado hay que aplicar schema a mano o recrear la base.

## Auth

- Login: `POST /api/v1/auth/login` (`person_id` + `password`) → JWT HS256 + refresh
- Roles: `admin|user|gate|officer|manager`
- Operador (`require_operator`): los cinco roles anteriores (incluye `user`)
- Solo admin: CRUD `/users`, `DELETE /visits/{id}`, `POST /fiscals/sync`, POST/PATCH/DELETE catálogo `/assets`
- `REQUIRE_AUTH` existe en config **pero no se lee** en `Depends`: las rutas protegidas siempre exigen JWT

Tras rotar `SECRET_KEY` hay que volver a iniciar sesión.

## Tests

```bash
uv run pytest
```

## Limitaciones conocidas (no ocultar)

- Refresh token se guarda en claro
- `verify_token` no recarga `is_active` ni `role` desde Postgres
- No hay ruta `/api/v1/files` en el router: fotos de visitas/bienes se persisten, pero la URL pública no sirve el archivo
- `POST /visits/` sigue exigiendo `BUCKET_NAME_S3` (o bucket Supabase) como metadato de foto aunque `STORAGE_PROVIDER=local`
