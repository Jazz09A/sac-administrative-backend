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

**Uso del token**
Para llamadas que en el futuro requieran autenticación, enviar cabecera:
`Authorization: Bearer <access_token>`

---

### Users
Rutas para administrar usuarios con rol administrador. El `id` es UUID4.

#### POST `/api/v1/users/`
Crea usuario administrador.

**Body**
```json
{
  "person_id": "19344555",
  "full_name": "Juan Perez",
  "email": "juan.perez@sac.gob.ve",
  "password": "Admin2026Seguro",
  "is_active": true
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
Actualiza `full_name`, `email`, `password` y/o `is_active`.

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

#### GET `/api/v1/contributors/{contributor_id}`
Obtiene contribuyente por ID interno.

#### PUT `/api/v1/contributors/{contributor_id}`
Actualiza contribuyente.

---

### Fiscals
#### GET `/api/v1/fiscals/?query=juan&limit=20`
Busca fiscales desde la copia local en PostgreSQL.

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
### Regla importante actual
Para registrar visita **no se envía `contributor_id`**.  
El request usa `contributor_name` y el backend:
- busca contribuyente por nombre,
- si no existe lo crea automáticamente con datos mínimos,
- valida `fiscal_id` contra la tabla local `fiscals` (debe existir y estar activo),
- `fiscal_id` puede venir como `id` local (ej: `"7"`) o como `external_id` UUID (ej: `"022f489c-0f44-4924-a616-b3a7586a60e6"`),
- registra la visita y devuelve el `id` de la visita en UUID.

#### POST `/api/v1/visits/`
Registrar ingreso.

**Body real de ejemplo**
```json
{
  "contributor_name": "Comercial ABC, C.A.",
  "responsible_person": "Maria Fernanda Ruiz",
  "fiscal_id": 7,
  "reason": "Entrega de expediente de fiscalizacion",
  "observations": "Trajo anexos completos",
  "department": "Fiscalizacion",
  "file_number": "EXP-2026-00045",
  "entry_date": "2026-04-17",
  "entry_time": "10:35:00",
  "signature_image_url": null
}
```

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
  "signature_image_url": null,
  "id": "49a5f2a5-889f-4739-bf38-b295d2df07ef",
  "fiscal_name": null,
  "exit_date": null,
  "exit_time": null,
  "status": "espera",
  "created_at": "2026-04-17T14:35:00.512000"
}
```

#### GET `/api/v1/visits/?status=espera&fiscal_id=7&skip=0&limit=20`
Lista visitas con filtros.

Parámetros disponibles:
- `contributor_id` (opcional)
- `rif` (opcional)
- `status` (opcional)
- `fiscal_id` (opcional)
- `entry_date` (opcional, formato `YYYY-MM-DD`)
- `skip` (default `0`)
- `limit` (default `100`)

#### GET `/api/v1/visits/history?rif=J-123&contribuyente=Comercial&registro=EXP-2026&departamento=Fiscalizacion&fecha_desde=2026-04-01&fecha_hasta=2026-04-30`
Historial de visitas para reporte administrativo.

Columnas de respuesta:
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
- `skip` (default `0`)
- `limit` (default `100`)

**Respuesta 200 (estructura)**
```json
[
  {
    "rif": "J-12345678-9",
    "contribuyente": "Comercial ABC, C.A.",
    "registro": "EXP-2026-00045",
    "depto": "Fiscalizacion",
    "motivo": "Entrega de expediente de fiscalizacion",
    "estado": "finalizado"
  }
]
```

#### GET `/api/v1/visits/{visit_id}`
Obtiene visita por ID UUID.

Ejemplo:
`GET /api/v1/visits/49a5f2a5-889f-4739-bf38-b295d2df07ef`

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

## Ejemplos rápidos con cURL

### 1) Login (JWT)
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"person_id":"19344555","password":"tu_contraseña"}'
```

### 2) Crear usuario administrador
```bash
curl -X POST "http://localhost:8000/api/v1/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "person_id": "19344555",
    "full_name": "Juan Perez",
    "email": "juan.perez@sac.gob.ve",
    "password": "Admin2026Seguro",
    "is_active": true
  }'
```

### 3) Sincronizar fiscales
```bash
curl -X POST "http://localhost:8000/api/v1/fiscals/sync"
```

### 4) Buscar fiscales
```bash
curl "http://localhost:8000/api/v1/fiscals?query=juan&limit=10"
```

### 5) Crear visita (sin contributor_id en request)
```bash
curl -X POST "http://localhost:8000/api/v1/visits/" \
  -H "Content-Type: application/json" \
  -d '{
    "contributor_name": "Comercial ABC, C.A.",
    "responsible_person": "Maria Fernanda Ruiz",
    "fiscal_id": 7,
    "reason": "Entrega de expediente de fiscalizacion",
    "entry_date": "2026-04-17",
    "entry_time": "10:35:00"
  }'
```

## Notas
- Errores comunes: `422` (validación), `404` (no encontrado), `400` (regla de negocio), `401` (login inválido).
- `visit_id` ahora es UUID.
- En `/docs`, el flujo OAuth2 usa `tokenUrl` `POST /api/v1/auth/login` para obtener el bearer token en pruebas interactivas.
- Última actualización de esta documentación: 2026-04-17.