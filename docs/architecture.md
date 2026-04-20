## docs/architecture.md

```markdown
# Arquitectura del Backend - Sistema Contribuyentes MVP

**Última modificación:** 2026-04-20 | **Cambios:** Historial de visitas con filtros parciales (`LIKE`) y visualización operativa de estados (`espera`/`atendido`). **Módulos tocados:** api/v1/visits.py, services/visit_service.py, infrastructure/postgres/visit_postgres_repository.py, docs/api_documentation.md.

## 1. Visión General
Aplicación **FastAPI** modular siguiendo **SOLID** (SRP, OCP, LSP, ISP, DIP) para registro/control de contribuyentes. Enfoque hexagonal: entidades puras -> repositorios -> controllers. **Postgres** async, **uv** deps.

**Principio:** Cada módulo tiene responsabilidad única. IAs/agentes: lean CLAUDE.md para generar código coherente.

## 2. Diagrama ER (Postgres)

```mermaid
erDiagram
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
    }
    PHOTOS {
        uuid id PK
        uuid visit_id FK
        varchar photo_url
        timestamp created_at
    }

    CONTRIBUTORS ||--o{ VISITS : "tiene"
    VISITS ||--o{ PHOTOS : "evidencia"
```

**Indexes clave:** rif (contributors), status+entry_date (visits).

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
| POST | `/contributors/` | Crea/busca por RIF | `ContributorOut` |
| GET | `/contributors/` | Lista/busca rif/nombre | `List[ContributorOut]` |
| GET | `/contributors/{id}` | Detalle | `ContributorOut` |
| POST | `/visits/` | Registro ingreso + foto | `VisitOut` |
| GET | `/visits/` | Filtros rif/fecha/status | `List[VisitOut]` |
| GET | `/visits/history` | Historial administrativo (RIF, contribuyente, registro, depto, motivo, estado) con filtros parciales y rango de fechas | `List[VisitHistoryItem]` |
| PATCH | `/visits/{id}/exit` | Registra salida | `VisitOut` |
| GET | `/dashboard/summary` | Métricas día (totales, en espera) | `DashboardSummary` |

**Regla operativa de estados en historial:** por defecto el historial lista solo visitas en `espera` y `atendido`; las `finalizado` se incluyen solo cuando el cliente envía `incluir_finalizados=true`.

**Autenticación:** JWT básico (funcionario), rol en future.

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