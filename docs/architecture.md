## docs/architecture.md

```markdown
# Arquitectura del Backend - Sistema Contribuyentes MVP

**Última modificación:** 2026-05-04 | **Cambios:** Soft delete en visitas (`deleted_at` + `DELETE /visits/{id}`), filtros para excluir borradas en listados/reportes y documentación explícita de patrón Strategy en storage. **Módulos tocados:** `src/models/visit.py`, `src/api/v1/visits.py`, `src/services/visit_service.py`, `src/infrastructure/postgres/visit_postgres_repository.py`, `src/infrastructure/storage/storage_factory.py`, `src/domain/repositories/file_storage_repository.py`, `docs/api_documentation.md`.

## 1. Visión General
Aplicación **FastAPI** modular siguiendo **SOLID** (SRP, OCP, LSP, ISP, DIP) para registro/control de contribuyentes. Enfoque hexagonal: entidades puras -> repositorios -> controllers. **Postgres** async, **uv** deps.

**Principio:** Cada módulo tiene responsabilidad única. IAs/agentes: lean CLAUDE.md para generar código coherente.

## 2. Diagrama ER (Postgres)

```mermaid
erDiagram
    USERS {
        uuid id PK
        varchar person_id UNIQUE
        varchar full_name
        varchar email UNIQUE
        varchar hashed_password
        varchar role "admin|user"
        boolean is_active
        timestamp last_login_at
        timestamp created_at
        timestamp updated_at
    }
    CONTRIBUTORS {
        uuid id PK
        varchar rif UNIQUE
        varchar name
        enum type "natural|juridica|representante|gestor"
        varchar occupation
        varchar phone
        varchar email
        timestamp created_at
        timestamp updated_at
    }
    VISITS {
        uuid id PK
        uuid contributor_id FK
        text reason
        text observations
        varchar received_by
        varchar department
        varchar file_number
        date entry_date
        time entry_time
        date exit_date
        time exit_time
        enum status "espera|atendido|finalizado|rechazado|reprogramado"
        varchar signature_image_url
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }
    PHOTOS {
        uuid id PK
        uuid visit_id FK
        varchar photo_url
        timestamp created_at
    }

    USERS ||--o{ VISITS : "registra"
    CONTRIBUTORS ||--o{ VISITS : "tiene"
    VISITS ||--o{ PHOTOS : "evidencia"
```

**Indexes clave:** rif (contributors), status+entry_date (visits), deleted_at (visits para exclusión por soft delete).

## 3. Capas Arquitectónicas (SOLID)

| Capa | Responsabilidad (SRP) | Ejemplos | DIP (Dependencias) |
|------|-----------------------|----------|--------------------|
| **Models** | Entidades DB puras | `Contributor(SQLModel)`, `VisitOut(BaseModel)` | SQLModel/Pydantic |
| **CRUD** | Lógica DB (repo pattern) | `get_contributor_by_rif(session: AsyncSession) -> Contributor|None` | Inyecta `AsyncSession` |
| **API** | Routes + validación | `router.post("/", response_model=VisitOut)` | Depends(get_db, get_current_user) |
| **Core** | Config/Infra cross-cut | `Settings`, `create_access_token` | Env vars |
| **Tests** | Verificación unit/int | `test_crud_get_by_rif`, `test_api_post_visit` | TestClient, override_get_db |

**Flujo request típico (registro ingreso):**
```
API (v1/visits.post) -> Depends(CRUD.create_visit) -> SQLModel.save -> 201 VisitOut
```

## 4. Endpoints MVP (OpenAPI auto-docs)

| Método | Endpoint | Descripción | Response |
|--------|----------|-------------|----------|
| POST | `/auth/login` | Login JWT (person_id + password) | `TokenResponse` |
| GET | `/auth/me` | Datos del usuario autenticado | `MeResponse` |
| POST | `/users/` | Crea usuario (admin/user) | `UserPublic` |
| GET | `/users/` | Lista usuarios | `List[UserPublic]` |
| GET | `/users/{id}` | Detalle usuario | `UserPublic` |
| PUT | `/users/{id}` | Actualiza usuario (incluye `role`) | `UserPublic` |
| DELETE | `/users/{id}` | Elimina usuario | `204` |
| POST | `/contributors/` | Crea/busca por RIF | `ContributorOut` |
| GET | `/contributors/` | Lista/busca rif/nombre | `List[ContributorOut]` |
| GET | `/contributors/{id}` | Detalle | `ContributorOut` |
| POST | `/visits/` | Registro ingreso + foto | `VisitOut` |
| GET | `/visits/` | Filtros rif/fecha/status | `List[VisitOut]` |
| GET | `/visits/reports/fiscals` | Reporte por fiscal con filtros por fecha, contribuyente, RIF, estado de visita y estado activo/inactivo del fiscal + paginación (`total/skip/limit/items`) | `FiscalVisitsReportResponse` |
| GET | `/visits/history` | Historial administrativo (RIF, contribuyente, registro, depto, motivo, estado, fiscal) con filtros parciales/rango de fechas y paginación (`total/skip/limit/items`) | `VisitHistoryReportResponse` |
| DELETE | `/visits/{id}` | Borrado lógico de visita (`soft delete`) | `204` |
| PATCH | `/visits/{id}/exit` | Registra salida | `VisitOut` |
| GET | `/dashboard/summary` | Métricas día (totales, en espera) | `DashboardSummary` |

**Regla operativa de estados en historial:** por defecto el historial lista solo visitas en `espera` y `atendido`; las `finalizado` se incluyen solo cuando el cliente envía `incluir_finalizados=true`.

**Regla de soft delete en visitas:** `deleted_at` marca borrado lógico. Las consultas operativas (`get/list/report/history/dashboard`) excluyen registros con `deleted_at` no nulo por defecto.

**Autenticación:** JWT HS256 con tabla `users`. Campo `role` soporta `admin` y `user`.

## 4.1 Patrones de diseño aplicados

- **Strategy (Storage Provider):**
  - Contrato: `FileStorageRepository` define `upload`, `delete` y `get_public_url`.
  - Estrategias concretas: `S3FileStorageRepository` y `SupabaseFileStorageRepository`.
  - Contexto/fábrica: `create_file_storage_repository(settings)` selecciona la estrategia según `settings.STORAGE_PROVIDER`.
  - Beneficio: desacopla la lógica de negocio del proveedor de almacenamiento y facilita extensión sin modificar servicios consumidores (OCP + DIP).

## 5. Buenas Prácticas Obligatorias
- **Pydantic everywhere**: `response_model=List[VisitPublic]`, `Body(VisitCreate)`.
- **Async todo**: `async def get_visits(...)`.
- **Error handling**: HTTPException(404, "Contribuyente no encontrado").
- **Tests 80%+**: `pytest --cov=src`.
- **Migrations**: `alembic revision --autogenerate -m "add visit status"`.

## 6. Deploy & DevOps
- **CI/CD**: GitHub Actions (uv sync -> test -> deploy Render).
- **Monitoring**: Prometheus? Future.

**Próximo cambio esperado:** formalizar transición de estados en endpoint dedicado de atención (paso a `atendido`) y desacoplar cierre administrativo (`finalizado`).
```

Este architecture.md es **referencia viva**: edítalo **siempre** post-cambio (ej. "2026-04-18 | Añadí auth. Módulos: core/security.py").