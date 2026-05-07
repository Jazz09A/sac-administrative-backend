# Documentación de API - Sistema Contribuyentes

## Arquitectura general
- Framework: FastAPI + SQLModel/Pydantic
- Base de datos: PostgreSQL (operativa) + MySQL/TiDB (fuente de fiscales)
- Autenticación (MVP):
  - Router montado en `/api/v1/auth` (ver sección **Auth**).
  - `POST /api/v1/auth/login` valida credenciales contra la tabla `users` usando `person_id` (cedula) + `password`.
  - Respuesta: JWT HS256 (`access_token`) y `refresh_token`.
  - El flag `REQUIRE_AUTH` en configuración está reservado para cuando los demás endpoints exijan el token; hoy el login ya emite JWT, pero las rutas de negocio no lo obligan de forma centralizada.
- Prefijo API: `/api/v1`

## Endpoints disponibles

### Health
#### GET `/health`
**Respuesta 200**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

### Auth
Rutas definidas en el router principal bajo prefijo `/auth` (tag `auth` en OpenAPI).

#### POST `/api/v1/auth/login`
Obtiene tokens para un administrador activo. Las credenciales se validan con la tabla `users` (`person_id` + password).

**Body**
```json
{
  "person_id": "19344555",
  "password": "tu_contraseña"
}
```

**Respuesta 200**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "Jf5v6VE0y...token_urlsafe...",
  "token_type": "bearer"
}
```

**Errores**
- `401`: usuario o contraseña incorrectos (`detail`: mensaje en español).
- `401`: usuario inactivo.
- `422`: cuerpo inválido (campos vacíos, longitud fuera de rango: `person_id` 1–20, `password` 1–256).

#### GET `/api/v1/auth/me`
Obtiene los datos del usuario autenticado. Requiere token JWT válido.

**Headers**
```
Authorization: Bearer <access_token>
```

**Respuesta 200**
```json
{
  "fullName": "Administrador del Sistema",
  "role": "admin",
  "username": "29675079"
}
```

**Errores**
- `401`: token inválido o no proporcionado.
- `404`: usuario no encontrado.

**Uso del token**
Para llamadas que en el futuro requieran autenticación, enviar cabecera:
`Authorization: Bearer <access_token>`

---

### Users
Rutas para administrar usuarios con roles (`admin` o `user`). El `id` es UUID4.

#### POST `/api/v1/users/`
Crea usuario administrador.

**Body**
```json
{
  "person_id": "19344555",
  "full_name": "Juan Perez",
  "email": "juan.perez@sac.gob.ve",
  "password": "Admin2026Seguro",
  "is_active": true,
  "role": "admin"
}
```

**Respuesta 201**
```json
{
  "id": "21dba487-264b-4f76-bb1a-38f6187ec4a0",
  "person_id": "19344555",
  "full_name": "Juan Perez",
  "email": "juan.perez@sac.gob.ve",
  "is_active": true,
  "role": "admin",
  "last_login_at": null,
  "created_at": "2026-04-17T16:20:11.102000",
  "updated_at": "2026-04-17T16:20:11.102000"
}
```

**Errores**
- `400`: cédula o email ya registrados.
- `422`: datos inválidos (`password` min 8).

#### GET `/api/v1/users/?skip=0&limit=100`
Lista usuarios administradores.

#### GET `/api/v1/users/{user_id}`
Obtiene usuario por UUID.

#### PUT `/api/v1/users/{user_id}`
Actualiza `full_name`, `email`, `password`, `is_active` y/o `role`.

#### DELETE `/api/v1/users/{user_id}`
Elimina el usuario (hard delete).

---

### Contributors
#### POST `/api/v1/contributors/`
Crea contribuyente manualmente por formulario administrativo.

**Body**
```json
{
  "rif": "J-12345678-9",
  "name": "Comercial ABC, C.A.",
  "type": "juridica",
  "occupation": "Comercio",
  "phone": "0412-5550000",
  "email": "admin@abc.com"
}
```

**Respuesta 201**
```json
{
  "rif": "J-12345678-9",
  "name": "Comercial ABC, C.A.",
  "type": "juridica",
  "occupation": "Comercio",
  "phone": "0412-5550000",
  "email": "admin@abc.com",
  "id": 12,
  "created_at": "2026-04-17T11:40:30.120000"
}
```

#### GET `/api/v1/contributors/?skip=0&limit=100`
Lista contribuyentes.

#### GET `/api/v1/contributors/search/{rif}`
Busca un contribuyente exacto por su RIF. Útil para autocompletar formularios en el frontend sin crear duplicados.
- Responde `200` con los datos del contribuyente si existe.
- Responde `404` si no se encuentra el contribuyente.

#### GET `/api/v1/contributors/{contributor_id}`
Obtiene contribuyente por ID interno.

#### PUT `/api/v1/contributors/{contributor_id}`
Actualiza contribuyente.

---

### Fiscals
#### GET `/api/v1/fiscals/?query=juan&skip=0&limit=20`
Busca fiscales desde la copia local en PostgreSQL.

Parámetros disponibles:
- `query` (opcional, búsqueda parcial por nombre o `external_id`)
- `skip` (opcional, default `0`)
- `limit` (opcional, default `100`)

**Respuesta 200**
```json
[
  {
    "id": 7,
    "external_id": "f4e3e034-3904-4af2-b737-0db6b72f6459",
    "name": "JUAN PEREZ",
    "person_id": 19344555,
    "email": "juan.perez@sac.gob.ve",
    "group_id": "9f2a8d4c-cc30-4a81-8a97-95e4b364f211",
    "supervisor_id": "4f9f7dca-8618-4eb8-9ba0-97f69193e31b",
    "status": true
  }
]
```

#### POST `/api/v1/fiscals/sync`
Sincroniza fiscales desde MySQL/TiDB a PostgreSQL.

**Respuesta 200 (sync exitosa)**
```json
{
  "started_at": "2026-04-17T15:10:11.100000",
  "finished_at": "2026-04-17T15:10:12.010000",
  "fetched_total": 155,
  "inserted_total": 22,
  "updated_total": 133,
  "skipped_total": 0,
  "duration_ms": 910,
  "status": "success",
  "error_message": null
}
```

**Respuesta 200 (sync fallida)**
```json
{
  "started_at": "2026-04-17T15:12:01.300000",
  "finished_at": "2026-04-17T15:12:02.100000",
  "fetched_total": 0,
  "inserted_total": 0,
  "updated_total": 0,
  "skipped_total": 0,
  "duration_ms": 800,
  "status": "failed",
  "error_message": "detalle del error de conexión o query"
}
```

#### GET `/api/v1/fiscals/sync/status`
Devuelve último estado de sincronización guardado.

---

### Visits
### Soft delete aplicado
- Las visitas usan borrado lógico con el campo `deleted_at`.
- `DELETE /api/v1/visits/{visit_id}` no elimina físicamente: asigna timestamp en `deleted_at`.
- Los listados/reportes de visitas excluyen por defecto registros con `deleted_at` no nulo.

### Regla importante actual
Para registrar visita **no se envía `contributor_id`**.  
El request usa **`contributor_rif`** (RIF fiscal real, obligatorio) y **`contributor_name`**. El backend:
- busca contribuyente por **RIF**; si no existe, lo crea con ese RIF y el nombre indicado (sin RIF temporales; valores que empiecen por `TEMP-` se rechazan),
- valida `fiscal_id` contra la tabla local `fiscals` (debe existir y estar activo),
- `fiscal_id` puede venir como `id` local (ej: `"7"`) o como `external_id` UUID (ej: `"022f489c-0f44-4924-a616-b3a7586a60e6"`),
- registra la visita y devuelve el `id` de la visita en UUID.

#### POST `/api/v1/visits/`
Registrar ingreso.

`Content-Type`: `multipart/form-data`

Campos de formulario:
- `contributor_rif` (texto, requerido; RIF fiscal real, máx. 20 caracteres; no se permiten prefijos `TEMP-`)
- `contributor_name` (texto, requerido)
- `responsible_person` (texto, requerido)
- `fiscal_id` (texto, requerido; acepta id local o external_id)
- `reason` (texto, requerido)
- `observations` (texto, opcional)
- `department` (texto, opcional)
- `file_number` (texto, opcional)
- `entry_date` (`YYYY-MM-DD`, requerido)
- `entry_time` (`HH:MM:SS`, requerido)
- `photo` (archivo, requerido; `image/jpeg`, `image/png`, `image/webp`)

**Respuesta 201 real (formato)**
```json
{
  "contributor_id": 12,
  "fiscal_id": 7,
  "reason": "Entrega de expediente de fiscalizacion",
  "observations": "Trajo anexos completos",
  "received_by": "Maria Fernanda Ruiz",
  "department": "Fiscalizacion",
  "file_number": "EXP-2026-00045",
  "entry_date": "2026-04-17",
  "entry_time": "10:35:00",
  "signature_image_url": "https://<accountid>.r2.cloudflarestorage.com/<bucket>/sac-administrative/sac-visits/49a5f2a5-889f-4739-bf38-b295d2df07ef/3f8d4e56-....png",
  "id": "49a5f2a5-889f-4739-bf38-b295d2df07ef",
  "fiscal_name": null,
  "exit_date": null,
  "exit_time": null,
  "status": "espera",
  "created_at": "2026-04-17T14:35:00.512000",
  "deleted_at": null,
  "photos": [
    {
      "visit_id": "49a5f2a5-889f-4739-bf38-b295d2df07ef",
      "photo_url": "https://<accountid>.r2.cloudflarestorage.com/<bucket>/sac-administrative/sac-visits/49a5f2a5-889f-4739-bf38-b295d2df07ef/3f8d4e56-....png",
      "id": 31,
      "created_at": "2026-04-20T15:02:10.000000"
    }
  ]
}
```

#### GET `/api/v1/visits/?status=espera&fiscal_id=7&skip=0&limit=20`
Lista visitas con filtros.

Regla de visibilidad:
- Excluye automáticamente visitas con `deleted_at` informado.

Parámetros disponibles:
- `contributor_id` (opcional)
- `rif` (opcional)
- `status` (opcional)
- `fiscal_id` (opcional)
- `entry_date` (opcional, formato `YYYY-MM-DD`; por defecto usa el d?a actual en zona horaria de Venezuela)
- `include_images` (opcional, `true|false`, default `false`; cuando es `true` agrega `photos` con `photo_url` por visita)
- `skip` (default `0`)
- `limit` (default `100`)

Ejemplo con imágenes:
`GET /api/v1/visits/?status=espera&include_images=true&skip=0&limit=20`

Comportamiento de respuesta:
- Si `include_images=false` (default), responde con `VisitPublic` (sin arreglo `photos`).
- Si `include_images=true`, responde con `VisitWithPhotosPublic` por cada elemento, incluyendo:
  - `photos[].visit_id`
  - `photos[].object_key`
  - `photos[].bucket`
  - `photos[].content_type`
  - `photos[].original_filename`
  - `photos[].size`
  - `photos[].id`
  - `photos[].created_at`
  - `photos[].photo_url` (URL pública calculada por backend)

#### GET `/api/v1/visits/reports/fiscals?fiscal_id=7&status_filter=espera,atendido&contributor_name=Comercial&rif=J-123&fiscal_status=true&date_from=2026-04-01&date_to=2026-04-30&skip=0&limit=20`
Reporte administrativo de visitas por fiscal, con filtros combinables y paginación.

Regla de visibilidad:
- Excluye automáticamente visitas con `deleted_at` informado.

Filtros disponibles:
- `fiscal_id` (opcional)
- `status_filter` (opcional, uno o varios estados separados por coma: `espera,atendido,finalizado,...`)
- `contributor_name` (opcional, búsqueda parcial case-insensitive)
- `rif` (opcional, búsqueda parcial case-insensitive)
- `fiscal_status` (opcional, `true`/`false` para estado activo/inactivo del fiscal)
- `date_from` (opcional, formato `YYYY-MM-DD`, aplica sobre `entry_date`)
- `date_to` (opcional, formato `YYYY-MM-DD`, aplica sobre `entry_date`)
  - Si no se env?a ninguno, el reporte usa por defecto el d?a actual en zona horaria de Venezuela (rango del mismo d?a).
- `q` (opcional, búsqueda parcial en nombre/rif del contribuyente)
- `skip` (default `0`)
- `limit` (default `100`)

**Respuesta 200 (estructura)**
```json
{
  "total": 238,
  "skip": 0,
  "limit": 20,
  "items": [
    {
      "visit_id": "49a5f2a5-889f-4739-bf38-b295d2df07ef",
      "fiscal_id": 7,
      "fiscal_name": "Maria Perez",
      "contributor_id": 12,
      "contributor_name": "Comercial ABC, C.A.",
      "contributor_rif": "J-12345678-9",
      "entry_date": "2026-04-17",
      "entry_time": "10:35:00",
      "exit_date": null,
      "exit_time": null,
      "status": "atendido",
      "reason": "Entrega de expediente de fiscalizacion",
      "department": "Fiscalizacion"
    }
  ]
}
```

#### GET `/api/v1/visits/history?rif=J-123&contribuyente=Comercial&registro=EXP-2026&departamento=Fiscalizacion&fecha_desde=2026-04-01&fecha_hasta=2026-04-30&incluir_finalizados=false&skip=0&limit=20`
Historial de visitas para reporte administrativo.

Comportamiento de estados:
- Por defecto (`incluir_finalizados=false`) solo devuelve `espera` y `atendido`.
- Si `incluir_finalizados=true`, también incluye visitas `finalizado`.

Regla de visibilidad:
- Excluye automáticamente visitas con `deleted_at` informado.

Columnas de respuesta:
- `id` (UUID de la visita)
- `rif`
- `contribuyente`
- `registro`
- `depto`
- `motivo`
- `estado`

Filtros disponibles:
- `rif` (búsqueda parcial, case-insensitive)
- `contribuyente` (búsqueda parcial por nombre del contribuyente, case-insensitive)
- `registro` (búsqueda parcial por número de expediente/registro, case-insensitive)
- `departamento` (búsqueda parcial en departamento del contribuyente, case-insensitive)
- `fecha_desde` (formato `YYYY-MM-DD`)
- `fecha_hasta` (formato `YYYY-MM-DD`)
  - Si no se env?a ninguno, el historial usa por defecto el d?a actual en zona horaria de Venezuela (rango del mismo d?a).
- `incluir_finalizados` (opcional, default `false`)
- `skip` (default `0`)
- `limit` (default `100`)

**Respuesta 200 (estructura)**
```json
{
  "total": 57,
  "skip": 0,
  "limit": 20,
  "items": [
    {
      "id": "49a5f2a5-889f-4739-bf38-b295d2df07ef",
      "rif": "J-12345678-9",
      "contribuyente": "Comercial ABC, C.A.",
      "registro": "EXP-2026-00045",
      "depto": "Fiscalizacion",
      "motivo": "Entrega de expediente de fiscalizacion",
      "estado": "atendido",
      "fiscal": "Maria Perez"
    }
  ]
}
```

#### GET `/api/v1/visits/{visit_id}`
Obtiene visita por ID UUID.

Regla de visibilidad:
- Si la visita fue borrada lógicamente (`deleted_at` con valor), responde como no encontrada (`404`).

Ejemplo:
`GET /api/v1/visits/49a5f2a5-889f-4739-bf38-b295d2df07ef`

Parámetros query:
- `include_images` (opcional, `true|false`, default `false`)
  - `false`: respuesta `VisitPublic`.
  - `true`: respuesta `VisitWithPhotosPublic` con arreglo `photos` y `photo_url`.

#### PATCH `/api/v1/visits/{visit_id}`
Corrige campos de una visita ya registrada (actualizacion parcial).

Campos editables (todos opcionales):
- `fiscal_id` (texto; acepta `id` local o `external_id`, igual que en el registro)
- `reason`
- `observations`
- `received_by`
- `department`
- `file_number`
- `entry_date` (`YYYY-MM-DD`)
- `entry_time` (`HH:MM:SS`)
- `exit_date` (`YYYY-MM-DD`)
- `exit_time` (`HH:MM:SS`)
- `status` (`espera`, `atendido`, `finalizado`, `rechazado`, `reprogramado`)

**Body ejemplo**
```json
{
  "reason": "Correccion de motivo",
  "department": "Recaudacion",
  "status": "atendido"
}
```

**Respuesta**
- Devuelve `VisitPublic`, incluyendo el fiscal asignado en:
  - `fiscal_id` (id local guardado)
  - `fiscal_name` (nombre del fiscal responsable)

**Errores tipicos**
- `400`: fiscal inexistente o inactivo
- `404`: visita no encontrada
- `422`: payload invalido

Nota:
- No permite actualizar visitas borradas lógicamente (responde `404`).

#### PATCH `/api/v1/visits/{visit_id}/exit`
Registra salida de visita.

**Body ejemplo**
```json
{
  "exit_date": "2026-04-17",
  "exit_time": "11:15:00",
  "status": "finalizado"
}
```

**Errores típicos**
- `400`: no se puede registrar salida (estado no permitido)
- `404`: visita no encontrada
- `422`: payload inválido

Nota:
- No permite registrar salida sobre visitas borradas lógicamente.

#### DELETE `/api/v1/visits/{visit_id}`
Aplica borrado lógico de visita (soft delete).

Comportamiento:
- Marca `deleted_at` con timestamp UTC.
- No elimina la fila de base de datos.
- Desde ese momento no aparece en listados/reportes estándar de visitas.

Respuestas:
- `204`: borrado lógico aplicado.
- `404`: visita no encontrada (incluye cuando ya está borrada).

---

### Dashboard
#### GET `/api/v1/dashboard/advanced`
Dashboard avanzado con métricas del día consultado.

Parámetros:
- `target_date` (opcional, formato `YYYY-MM-DD`). Si no se envía, usa la fecha actual.

**Respuesta 200 (estructura)**
```json
{
  "date": "2026-04-17",
  "totals": {
    "entries": 24,
    "in_waiting": 7,
    "finished": 17
  },
  "comparison": {
    "vs_previous_day_pct": 12.5
  },
  "latest_visits": [
    {
      "id": "49a5f2a5-889f-4739-bf38-b295d2df07ef",
      "contributor_name": "Comercial ABC, C.A.",
      "fiscal_id": 7,
      "status": "espera",
      "entry_time": "10:35:00"
    }
  ]
}
```

---

### WebSocket (tiempo real)
Canal para dashboard en tiempo real de visitas (ingresos, atención, salida, edición y borrado lógico).

#### WS `/api/v1/ws/visits`
- Protocolo: `ws://` (local) o `wss://` (producción).
- Objetivo: publicar eventos de visitas para clientes conectados.
- El backend emite mensajes JSON con estructura:

```json
{
  "type": "visit.created",
  "occurred_at": "2026-05-05T13:15:09.214000+00:00",
  "payload": {}
}
```

Eventos disponibles:
- `visit.created`: emitido al crear ingreso (`POST /api/v1/visits/`).
- `visit.attended`: emitido al marcar visita atendida (`PATCH /api/v1/visits/{visit_id}/attend`).
- `visit.updated`: emitido al editar una visita (`PATCH /api/v1/visits/{visit_id}`).
- `visit.exited`: emitido al registrar salida (`PATCH /api/v1/visits/{visit_id}/exit`).
- `visit.deleted`: emitido al aplicar soft delete (`DELETE /api/v1/visits/{visit_id}`), payload mínimo:

```json
{
  "id": "49a5f2a5-889f-4739-bf38-b295d2df07ef"
}
```

Nota de payload:
- Para `visit.created`, `visit.attended`, `visit.updated` y `visit.exited`, el `payload` corresponde al modelo público de visita que devuelve la API (`VisitWithPhotosPublic` o `VisitPublic`), serializado a JSON.
  - Incluye `contributor_name` para identificar el contribuyente en el cliente en tiempo real.
- Para `visit.deleted`, el `payload` solo incluye el `id` de la visita.

#### Test manual realtime (frontend conectado)
Endpoint util para pruebas manuales en local:

`POST /api/v1/ws/visits/test-notification`

Body:
```json
{
  "event_type": "visit.test",
  "payload": {
    "message": "ping desde backend",
    "source": "manual-test"
  }
}
```

Reglas:
- Disponible solo en entorno `local/development`.
- Publica el evento en el mismo canal WS (`/api/v1/ws/visits`) donde escucha el frontend.

Ejemplo cURL:
```bash
curl -X POST "http://localhost:8000/api/v1/ws/visits/test-notification" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "visit.test",
    "payload": {
      "message": "ping desde backend",
      "source": "manual-test"
    }
  }'
```

## Ejemplos rápidos con cURL

### 1) Login (JWT)
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"person_id":"19344555","password":"tu_contraseña"}'
```

### 2) Obtener datos del usuario autenticado (/me)
```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer <access_token>"
```

**Respuesta:**
```json
{
  "fullName": "Administrador del Sistema",
  "role": "admin",
  "username": "29675079"
}
```

### 3) Crear usuario administrador
```bash
curl -X POST "http://localhost:8000/api/v1/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": "19344555",
    "full_name": "Juan Perez",
    "email": "juan.perez@sac.gob.ve",
    "password": "Admin2026Seguro",
    "is_active": true,
    "role": "admin"
  }'
```

**Nota:** El campo `role` acepta valores `"admin"` o `"user"` (default: `"user"`).

### 4) Sincronizar fiscales
```bash
curl -X POST "http://localhost:8000/api/v1/fiscals/sync"
```

### 5) Buscar fiscales
```bash
curl "http://localhost:8000/api/v1/fiscals?query=juan&limit=10"
```

### 6) Crear visita (sin contributor_id en request)
```bash
curl -X POST "http://localhost:8000/api/v1/visits/" \
  -F "contributor_rif=J-12345678-9" \
  -F "contributor_name=Comercial ABC, C.A." \
  -F "responsible_person=Maria Fernanda Ruiz" \
  -F "fiscal_id=7" \
  -F "reason=Entrega de expediente de fiscalizacion" \
  -F "entry_date=2026-04-17" \
  -F "entry_time=10:35:00" \
  -F "photo=@C:/ruta/imagen.png"
```

## Notas
- Errores comunes: `422` (validación), `404` (no encontrado), `400` (regla de negocio), `401` (login inválido).
- `visit_id` ahora es UUID.
- Visitas usan soft delete con `deleted_at`; para depuración/auditoría se conserva el registro.
- En `/docs`, el flujo OAuth2 usa `tokenUrl` `POST /api/v1/auth/login` para obtener el bearer token en pruebas interactivas.
- Última actualización de esta documentación: 2026-05-05.
- **Cambios recientes:**
  - Nuevo canal WebSocket `WS /api/v1/ws/visits` para eventos en tiempo real de visitas (`visit.created`, `visit.attended`, `visit.updated`, `visit.exited`, `visit.deleted`).
  - Soft delete en visitas: nuevo `DELETE /api/v1/visits/{visit_id}`, nuevo campo `deleted_at`, y filtros para excluir eliminadas en listados/reportes.
  - Patrón Strategy en almacenamiento de archivos: selección de proveedor (`s3`/`supabase`) mediante `create_file_storage_repository` y contrato `FileStorageRepository`.
  - Agregado campo `role` en modelo `User` (valores: `admin`, `user`).
  - Nuevo endpoint `GET /api/v1/auth/me` para obtener datos del usuario autenticado.
  - Registro de visita (`POST /api/v1/visits/`): campo obligatorio `contributor_rif` (RIF real); ya no se generan RIF temporales `TEMP-…`.