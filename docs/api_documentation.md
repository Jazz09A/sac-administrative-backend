# Documentación de API — SENIAT administrativa

Contrato leído de `src/api/v1/*.py` (2026-08-17, TASK-001–003). Prefijo `/api/v1`. OpenAPI runtime en `/docs`; este archivo no es un spec OpenAPI completo.

Auth por defecto: `Authorization: Bearer <access_token>`. Login y `GET /health` son públicos.

Roles: `admin|user|gate|officer|manager`. **Operador** = los cinco (`require_operator`). **Admin** = solo `admin`.

---

## Health

### GET `/health`

Público. `{ "status": "healthy", "version": "..." }`.

---

## Auth

Router `/auth`. Login público; `/me` exige JWT.

### POST `/api/v1/auth/login`

Body JSON: `{ "person_id": "...", "password": "..." }`.

Respuesta 200: `access_token`, `refresh_token`, `token_type=bearer`, `role`, `full_name`.

Errores: `401` credenciales o usuario inactivo; `422` validación.

El refresh se persiste en claro en `users.refresh_token`. No hay endpoint de refresh en este router.

### GET `/api/v1/auth/me`

Respuesta 200:

```json
{
  "id": "uuid-del-usuario",
  "fullName": "...",
  "full_name": "...",
  "role": "admin",
  "username": "person_id",
  "person_id": "person_id"
}
```

`id` (UUID) es el que usa la garita como `carrier_user_id` / asignarme. Tras rotar JWT hay que volver a iniciar sesión.

---

## Users (admin)

Router `/users`. Todas las rutas `require_admin`.

| Método | Ruta | Notas |
|--------|------|--------|
| POST | `/api/v1/users/` | Alta. `role` regex `admin\|user\|gate\|officer\|manager`. `password` min 8. 400 si cédula o email duplicados |
| GET | `/api/v1/users/` | Lista `skip`/`limit` |
| GET | `/api/v1/users/{user_id}` | UUID |
| PUT | `/api/v1/users/{user_id}` | `full_name`, `email`, `password`, `is_active`, `role` |
| DELETE | `/api/v1/users/{user_id}` | Hard delete, 204 |

---

## Contributors (operador)

Router `/contributors`. `cedula` unique nullable. `rif` unique nullable (Postgres permite varios NULL). `name` nullable. Validadores rechazan RIF `TEMP-*`; no hay placeholders `PEND-`.

| Método | Ruta | Notas |
|--------|------|--------|
| POST | `/api/v1/contributors/` | Crea o retorna existente: primero por cédula, luego por RIF |
| GET | `/api/v1/contributors/` | Lista `skip`/`limit` |
| GET | `/api/v1/contributors/search/{rif}` | 404 si no existe. Incluye `last_fiscal_id` y `last_reason` de la última visita |
| GET | `/api/v1/contributors/{contributor_id}` | id entero |
| PUT | `/api/v1/contributors/{contributor_id}` | name, type, cedula, occupation, phone, email |

No hay query `?rif=` en el listado (el search es por path).

---

## Fiscals (operador; sync = admin)

| Método | Ruta | Auth extra | Notas |
|--------|------|------------|--------|
| GET | `/api/v1/fiscals/` | operador | `query`, `skip`, `limit` |
| GET | `/api/v1/fiscals/{fiscal_id}` | operador | 404 si no existe |
| POST | `/api/v1/fiscals/sync` | **admin** | Copia MySQL/TiDB → Postgres |
| GET | `/api/v1/fiscals/sync/status` | operador | 404 si no hay corridas |

---

## Visits (operador; delete = admin)

Router `/visits` con `require_operator` en el router. Soft delete: `deleted_at`; listados operativos lo excluyen.

Estados: `espera`, `en_atencion`, `atendido`, `incompleto`, `remitido`, `finalizado`, `rechazado`, `reprogramado`.

### POST `/api/v1/visits/`

Ingreso. `multipart/form-data`. Foto **obligatoria**.

Obligatorios: `contributor_cedula`, `department`, `photo`.

Opcionales: `contributor_rif`, `contributor_name`, `fiscal_id` (id local o `external_id`), `responsible_person`, `reason`, `observations`, `file_number`, `entry_date`, `entry_time`.

La garita envía solo cédula + departamento + foto. RIF `TEMP-*` se rechaza si llega.

Efectos: crea/busca contribuyente **por cédula**; asigna `ticket_no` `T-YYYYMMDD-NNNN` con `pg_advisory_xact_lock` + unique index; status `espera`; publica `visit.created`.

Conflictos de ticket o RIF duplicado: `409`.

Limitación: el handler exige `BUCKET_NAME_S3` o `BUCKET_NAME_SUPABASE` según provider **distinto de supabase** (el `else` cubre `local` y `s3`). Con `STORAGE_PROVIDER=local` y bucket vacío responde 500 aunque el disco local exista.

### GET `/api/v1/visits/`

Filtros: `contributor_id`, `cedula`, `rif`, `status`, `fiscal_id`, `entry_date` (default hoy America/Caracas **salvo** `open=true`), `open`, `include_images`, `skip`, `limit`.

`open=true`: visitas sin `exit_at` y no `finalizado`. **No** aplica el default de fecha de hoy (`entry_date` explícito sí gana). Usado por la garita de salida: `GET /api/v1/visits/?cedula=...&open=true`.

Cada `VisitPublic` incluye `wait_seconds`, `attention_seconds`, `stay_seconds` (este último = `exit_at` − ingreso; `None` si no hay salida).

### GET `/api/v1/visits/history`

Historial paginado. Default `incluir_finalizados=true` (todas las no borradas). Si `false`, solo `espera` y `atendido`. Fechas default: hoy VE.

### GET `/api/v1/visits/queue`

Cola operativa (`department` opcional).

### GET `/api/v1/visits/metrics`

Métricas del día (`target_date` opcional, default hoy VE): `waiting`, `in_service`, `closed`, `exited`, promedios `avg_wait_seconds`, `avg_attention_seconds`, `avg_stay_seconds`.

### GET `/api/v1/visits/reports/fiscals`

Reporte por fiscal. Si no hay fechas, rango = hoy VE. Filtros: `fiscal_id`, `status_filter` (coma), `contributor_name`, `rif`, `fiscal_status`, `date_from`, `date_to`, `q`, `skip`, `limit`.

### GET `/api/v1/visits/{visit_id}`

404 si no existe o está soft-deleted. `include_images` opcional.

### PATCH `/api/v1/visits/{visit_id}/call`

`espera` → `en_atencion` + `called_at`. Evento `visit.called`. Taquilla usa este path para “Llamar”.

### PATCH `/api/v1/visits/{visit_id}/intake`

Body JSON: `{ "name": "...", "reason": "...", "rif"? }`. Actualiza `Contributor.name` (y `rif` si viene) y `Visit.reason`. Evento `visit.updated`. `409` si el RIF ya pertenece a otro contribuyente. Rechaza RIF `TEMP-*`.

### PATCH `/api/v1/visits/{visit_id}/close`

Body: `{ "status": "atendido" | "incompleto" | "remitido", "observations"? }`. Solo desde `en_atencion`. Exige que el contribuyente tenga **nombre** y la visita **motivo** (normalmente cargados vía `/intake`). Evento `visit.closed`.

### PATCH `/api/v1/visits/{visit_id}/exit`

Siempre deja status `finalizado` + `exit_at`. Permitido desde `espera|en_atencion|atendido|incompleto|remitido`. Evento `visit.exited`. Body opcional `exit_date` / `exit_time` / `status` (el status del body **no** gana: el servicio fuerza `finalizado`). La respuesta incluye `stay_seconds`.

### PATCH `/api/v1/visits/{visit_id}/attend`

Legado: `espera` → `atendido`. Evento `visit.attended`. **No usar en taquilla nueva** (`/desk` llama `/call`, `/intake` y `/close`).

### PATCH `/api/v1/visits/{visit_id}`

Corrección parcial. Campos en `VisitUpdate`: `fiscal_id`, `reason`, `observations`, `received_by`, `department`, `file_number`, `entry_date`, `entry_time`, `exit_date`, `exit_time`. Extra se ignora: **no cambia `status`**. Evento `visit.updated`.

### DELETE `/api/v1/visits/{visit_id}`

Admin. Soft delete. 204. Evento `visit.deleted` con `{ "id": "..." }`.

---

## Biometrics (operador)

Imagen base64 (data URL o raw). Magic bytes JPEG/PNG/WEBP. Máx. 10 MB. `landmarks` 400–478 puntos.

### POST `/api/v1/biometrics/recognize`

Body: `{ "image", "landmarks", "glasses"? }`.

Respuesta: `result`, `message`, `contributor_id`, `rif`, `cedula`, `confidence`, `fallback`, `region_used`, `occlusion` `{ mouth, left_eye, right_eye }`.

Resultados relevantes: `recognized`, `unknown`, `no_face`, `bad_pose`, `no_gallery`, `needs_document`, `calibration_required`.

Comportamiento: boca ocluida → periocular; `glasses=true` filtra plantillas glasses si hay; ambos ojos no visibles → `needs_document` + `fallback=cedula_rif` (nombre del flag en API; el kiosko pide **solo cédula**). Motor LBPH. No ArcFace/GPU.

### POST `/api/v1/biometrics/enroll`

201. Body: `image`, `landmarks`, `cedula` (**obligatoria**), `rif?`, `name?`, `glasses?`. Crea/actualiza contribuyente por cédula y plantillas `full|periocular|nose`. El kiosko de garita **no** envía RIF ni nombre. RIF `TEMP-*` se rechaza.

---

## Assets — patrimonio institucional (operador; catálogo write = admin)

Solo equipos/mobiliario SENIAT. **Sin** `contributor_id` en el bien. `carrier_user_id` = funcionario (`users.id`). `visit_id` opcional en movimientos.

| Método | Ruta | Auth | Notas |
|--------|------|------|--------|
| GET | `/api/v1/assets/alerts/open-out` | operador | `visit_id?` query |
| GET | `/api/v1/assets/export.csv` | operador | `text/csv`, filename `seniat-assets.csv`. No Excel/PDF |
| POST | `/api/v1/assets/` | **admin** | 409 código/serial duplicado |
| GET | `/api/v1/assets/` | operador | `status`, `q`, `skip`, `limit` |
| GET | `/api/v1/assets/{asset_id}` | operador | |
| PATCH | `/api/v1/assets/{asset_id}` | **admin** | |
| DELETE | `/api/v1/assets/{asset_id}` | **admin** | 204 |
| POST | `/api/v1/assets/{asset_id}/photo` | operador | JPEG/PNG/WEBP ≤10 MB. Persiste `photo_object_key`. **No hay GET de archivo** |
| POST | `/api/v1/assets/{asset_id}/assign` | operador | `{ "user_id", "workstation"? }` |
| POST | `/api/v1/assets/{asset_id}/release` | operador | |
| POST | `/api/v1/assets/{asset_id}/movements` | operador | `{ "direction": "out"\|"in", "carrier_user_id", "visit_id"?, "notes"? }` |

Estados del bien: `in_sede`, `assigned`, `in_transit_out`.

No documentar la foto de bien como visible al recargar: `LOCAL_STORAGE_PUBLIC_URL=/api/v1/files` no está montada en el router.

---

## Dashboard (operador)

### GET `/api/v1/dashboard/advanced`

`target_date` opcional. Payload: `date`, `visitas_en_curso`, `entradas_dia` (hoy/ayer/`porcentaje_cambio`), `personas_dentro` (actual/hora_anterior/`porcentaje_cambio`), `visitas_atendidas` (**conteo de ingresos del día**, no de cierres), `visitas_pendientes` (status `espera`), `ultimas_actividades`.

No existe `GET /dashboard/summary`.

Para ocupación/tiempos de cola usar `GET /visits/metrics`.

---

## WebSocket

### WS `/api/v1/ws/visits`

Token: query `access_token` **o** header `Authorization: Bearer`. Si falta o el rol no es operador: cierra con código **4401**.

Mensaje: `{ "type": "<evento>", "occurred_at": "<ISO UTC>", "payload": ... }`.

Eventos de flujo nuevo: `visit.created`, `visit.called`, `visit.closed`, `visit.exited`, `visit.updated`. También se publican `visit.attended` (legado `/attend`) y `visit.deleted`.

### POST `/api/v1/ws/visits/test-notification`

JWT (cualquier usuario autenticado vía `get_current_user`). Solo si `ENVIRONMENT` es `local`/`development`/`dev`; si no, 403. Body: `{ "event_type"?, "payload"? }`.

---

## Flags de config que no hacen lo que el nombre sugiere

- `REQUIRE_AUTH`: no se lee en Depends. JWT sigue activo en rutas protegidas aunque se ponga `false`.
- `LOCAL_STORAGE_PUBLIC_URL`: se usa al **construir** URLs, no implica que FastAPI sirva esos paths.
