# Arquitectura — API administrativa SENIAT

**Última modificación:** 2026-08-17 | TASK-001–003 (alta por cédula, intake en taquilla, salida abierta) documentados contra routers en `src/api/v1/`.

## 1. Visión

Un Postgres, una API FastAPI (`sac-administrative-backend/`), una web Next.js (`sac-access-control/`) en LAN on-premise.

Identidad en alta de garita: **cédula + plantilla facial**. RIF y nombre se completan en taquilla (`PATCH /visits/{id}/intake`). FACE-R (`app/`) es prototipo del motor; el kiosko de producto es Next `/gate` (MediaPipe local).

Storage **local por defecto**. S3/Supabase no son obligatorios.

## 2. Límites de sistema

| Hay | No hay (esta iteración) |
|-----|-------------------------|
| JWT en biometrics, visits, contributors, dashboard, fiscals, assets, WS | Ticket térmico |
| Bienes = patrimonio institucional (`seniat_assets*`) | Pertenencias del contribuyente en bienes |
| Export CSV de bienes (stdlib `csv`) | Excel / PDF |
| LBPH + recortes periocular/nariz | ArcFace / GPU |
| `create_all` + unique index de ticket al arranque | Migraciones Alembic versionadas en git |

`alembic/` está gitignored. `create_all` **no ALTER** un Postgres ya creado: columnas nuevas (p. ej. `ticket_no`, `cedula`, tablas de bienes) y nullability de `Contributor.rif`/`name` y `Visit.reason` no aparecen solas en una base vieja. Recrear Postgres o ALTER manual.

## 3. Diagrama de dominio (Postgres)

```mermaid
erDiagram
    USERS {
        uuid id PK
        varchar person_id UNIQUE
        varchar role "admin|user|gate|officer|manager"
        varchar refresh_token
        boolean is_active
    }
    CONTRIBUTOR {
        int id PK
        varchar rif UNIQUE "nullable; unique permite NULL"
        varchar cedula UNIQUE "nullable"
        varchar name "nullable"
    }
    FACE_TEMPLATES {
        int id PK
        int contributor_id FK
        varchar region "full|periocular|nose"
        boolean glasses
        bytes embedding
    }
    VISIT {
        uuid id PK
        int contributor_id FK
        int fiscal_id FK "nullable"
        varchar ticket_no UNIQUE "T-YYYYMMDD-NNNN"
        varchar reason "nullable"
        varchar status "espera|en_atencion|atendido|incompleto|remitido|finalizado|..."
        datetime called_at
        datetime closed_at
        datetime exit_at
        datetime deleted_at
    }
    PHOTO {
        int id PK
        uuid visit_id FK
        varchar object_key
        varchar bucket
    }
    SENIAT_ASSETS {
        uuid id PK
        varchar inventory_code UNIQUE
        varchar serial UNIQUE
        varchar status "in_sede|assigned|in_transit_out"
        uuid assigned_user_id FK
        varchar photo_object_key
    }
    SENIAT_ASSET_ASSIGNMENTS {
        int id PK
        uuid asset_id FK
        uuid user_id FK
    }
    SENIAT_ASSET_MOVEMENTS {
        uuid id PK
        uuid asset_id FK
        uuid carrier_user_id FK
        uuid visit_id FK "opcional"
        varchar direction "out|in"
        varchar status "open|closed"
    }

    CONTRIBUTOR ||--o{ VISIT : tiene
    CONTRIBUTOR ||--o{ FACE_TEMPLATES : galeria
    VISIT ||--o{ PHOTO : evidencia
    USERS ||--o{ SENIAT_ASSET_ASSIGNMENTS : funcionario
    SENIAT_ASSETS ||--o{ SENIAT_ASSET_ASSIGNMENTS : asignacion
    SENIAT_ASSETS ||--o{ SENIAT_ASSET_MOVEMENTS : movimiento
    VISIT ||--o{ SENIAT_ASSET_MOVEMENTS : traza_opcional
```

El bien **no** tiene `contributor_id`. Un movimiento puede ligarse a una visita solo para trazar salida/retorno de equipo SENIAT.

## 4. Capas

| Capa | Rol | Ejemplos |
|------|-----|----------|
| API | Rutas FastAPI | `src/api/v1/{auth,visits,biometrics,assets,ws,...}.py` |
| Servicios | Flujo de negocio | `VisitService`, `AssetService`, `services/biometrics/` |
| Repositorios | Postgres / disco | `visit_postgres_repository`, `local_repository` |
| Modelos | SQLModel | `visit`, `contributor`, `face_template`, `asset`, `user` |
| Core | Config, JWT, DB | `config.py`, `security.py`, `database.py` |
| Realtime | Broadcast WS | `src/realtime/visit_ws_manager.py` |

Prefijo: `API_V1_STR=/api/v1` (`main.py` incluye `api_router`). Health: `GET /health` (público).

## 5. Auth y roles

- JWT HS256. Login público: `POST /api/v1/auth/login`.
- `OPERATOR_ROLES` = `admin|user|gate|officer|manager`. `require_operator` incluye los cinco (también `user`).
- `require_admin`: solo `admin` — CRUD users, delete visita, `POST /fiscals/sync`, POST/PATCH/DELETE catálogo bienes.
- `GET /api/v1/auth/me` incluye `id` (UUID) para carrier / “asignarme”.
- `REQUIRE_AUTH` en settings **no se consulta** en Depends: las rutas con `require_*` siempre piden JWT.

Deuda media conocida:

- Refresh token en claro (`users.refresh_token`)
- `verify_token` no recarga `is_active`/`role` desde DB
- BFF Next `GET /api/auth/session` entrega el JWT al JS (superficie XSS)
- Tras cambiar el secreto JWT hay que volver a iniciar sesión

## 6. Storage

Estrategia: `FileStorageRepository` + fábrica (`STORAGE_PROVIDER`: `local` | `s3` | `supabase`).

Local (`src/infrastructure/storage/local_repository.py`):

- Base: `LOCAL_STORAGE_PATH` (default `data/storage`)
- Rechaza keys absolutas y segmentos `..`
- `get_public_url` arma `{LOCAL_STORAGE_PUBLIC_URL}/{key}` (default `/api/v1/files/...`)

**Hueco:** no existe router que sirva `/api/v1/files`. Las fotos se escriben a disco; no documentar “la foto se ve al recargar” como comportamiento actual.

**Hueco visitas:** `POST /visits/` aún exige `BUCKET_NAME_S3` o `BUCKET_NAME_SUPABASE` como metadato aunque el provider sea `local`. El archivo sí puede ir a disco; el bucket vacío aborta el ingreso con 500.

## 7. Flujo de visitas (taquilla nueva)

1. Garita `POST /visits/` (cédula + foto + departamento; RIF/nombre/motivo/fiscal opcionales y el kiosko no los envía) → `ticket_no` `T-YYYYMMDD-NNNN` (lock `pg_advisory_xact_lock` + unique index) + status `espera`
2. Cola `GET /visits/queue` (UI: etiqueta = nombre o, si falta, cédula)
3. Llamar `PATCH /visits/{id}/call` → `en_atencion` + `called_at`
4. Intake `PATCH /visits/{id}/intake` `{name, reason, rif?}`
5. Cerrar `PATCH /visits/{id}/close` `{status: atendido|incompleto|remitido}` + `closed_at` (exige nombre y motivo)
6. Salida: `GET /visits/?cedula=...&open=true` (sin default de hoy; abiertas = sin `exit_at` y no `finalizado`). Si hay una sola, la garita hace `PATCH /visits/{id}/exit` automático. Exit → **siempre** `finalizado` + `exit_at` (permitido desde `espera|en_atencion|atendido|incompleto|remitido`). `stay_seconds` en `VisitPublic`.

`PATCH /visits/{id}/attend` existe (espera → atendido, evento `visit.attended`) para consola vieja. **No usarlo en taquilla nueva.**

No hay RIF sintético `TEMP-`/`PEND-` en el flujo.

## 8. Biometría

`POST /api/v1/biometrics/recognize` y `/enroll` (operador). Imagen base64: magic bytes JPEG/PNG/WEBP, máx. 10 MB, landmarks 400–478.

- Enroll: **cédula obligatoria**; `rif` y `name` opcionales. El kiosko no los envía.
- Boca ocluida → región periocular
- Hint `glasses` filtra plantillas con flag glasses
- Ambos ojos no visibles → `needs_document` + `fallback=cedula_rif` (el kiosko pide solo cédula)
- Motor: OpenCV LBPH. No ArcFace/GPU

## 9. Bienes institucionales

CRUD `/api/v1/assets`, foto, assign, release, movements `out|in` (`carrier_user_id` = funcionario, `visit_id` opcional), `GET /alerts/open-out`, `GET /export.csv`.

Alta/edición/baja del catálogo: admin. Consulta y movimientos: operador.

## 10. Tiempo real

`WS /api/v1/ws/visits`. Token: query `access_token` o header `Authorization: Bearer`. Código de cierre `4401` si el token es inválido o el rol no es operador.

Eventos publicados desde visitas: `visit.created`, `visit.called`, `visit.closed`, `visit.exited`, `visit.updated`, más legado `visit.attended` y `visit.deleted`.

Mensaje: `{ type, occurred_at, payload }`. `POST /ws/visits/test-notification` solo si `ENVIRONMENT` es local/dev.
