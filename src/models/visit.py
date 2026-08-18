"""
Visit model: ingreso/salida + status flow.
Última mod: 2026-04-17 09:01 | Changes: Status enum, relations to Contributor/Photo.
"""
from datetime import UTC, date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ConfigDict, field_validator, model_validator
from pydantic import Field as PydanticField
from sqlmodel import Field, Relationship, SQLModel

from src.models.photo import PhotoPublic

try:
    VENEZUELA_TZ = ZoneInfo("America/Caracas")
except ZoneInfoNotFoundError:
    VENEZUELA_TZ = timezone(timedelta(hours=-4))


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def visit_duration_metrics(
    *,
    entry_date: date,
    entry_time: time,
    called_at: datetime | None,
    closed_at: datetime | None,
    exit_at: datetime | None,
) -> dict[str, int | None]:
    """Duraciones calculadas; None si falta el timestamp de cierre del tramo."""
    entry_utc = datetime.combine(entry_date, entry_time, tzinfo=VENEZUELA_TZ).astimezone(
        UTC
    )
    called = _as_utc(called_at)
    closed = _as_utc(closed_at)
    exited = _as_utc(exit_at)
    return {
        "wait_seconds": int((called - entry_utc).total_seconds()) if called is not None else None,
        "attention_seconds": (
            int((closed - called).total_seconds())
            if called is not None and closed is not None
            else None
        ),
        "stay_seconds": int((exited - entry_utc).total_seconds()) if exited is not None else None,
    }

class VisitStatus(str, Enum):
    """Flujo operativo Garita → Taquilla → Salida."""
    ESPERA = "espera"
    EN_ATENCION = "en_atencion"
    ATENDIDO = "atendido"
    INCOMPLETO = "incompleto"
    REMITIDO = "remitido"
    FINALIZADO = "finalizado"
    RECHAZADO = "rechazado"
    REPROGRAMADO = "reprogramado"

class VisitBase(SQLModel):
    contributor_id: Optional[int] = PydanticField(default=None, gt=0, description="FK interno")
    fiscal_id: Optional[int] = PydanticField(default=None, gt=0, description="FK fiscal local")
    reason: Optional[str] = PydanticField(default=None, max_length=500)
    observations: Optional[str] = Field(default=None, max_length=1000)
    received_by: Optional[str] = Field(default=None, max_length=255)
    department: Optional[str] = Field(default=None, max_length=255)
    file_number: Optional[str] = Field(default=None, max_length=100)
    entry_date: date
    entry_time: time
    ticket_no: Optional[str] = Field(default=None, max_length=32)
    called_at: Optional[datetime] = Field(default=None)
    closed_at: Optional[datetime] = Field(default=None)
    exit_at: Optional[datetime] = Field(default=None)
    signature_image_url: Optional[str] = Field(default=None, max_length=500)

class VisitCreate(SQLModel):
    contributor_cedula: str = PydanticField(
        ...,
        min_length=1,
        max_length=20,
        description="Cédula de identidad; clave de reutilización del contribuyente",
    )
    contributor_rif: Optional[str] = PydanticField(
        default=None,
        max_length=20,
        description="RIF opcional (se rechaza TEMP-*)",
    )
    contributor_name: Optional[str] = PydanticField(default=None, max_length=255)
    fiscal_id: Optional[str] = PydanticField(
        default=None,
        max_length=255,
        description="Identificador fiscal opcional: id local o external_id",
    )
    responsible_person: Optional[str] = PydanticField(default=None, max_length=255)
    reason: Optional[str] = PydanticField(default=None, max_length=500)
    observations: Optional[str] = Field(default=None, max_length=1000)
    department: str = PydanticField(..., min_length=1, max_length=255)
    file_number: Optional[str] = Field(default=None, max_length=100)
    entry_date: Optional[date] = None
    entry_time: Optional[time] = None
    signature_image_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("contributor_cedula", "department")
    @classmethod
    def strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("campo obligatorio")
        return stripped

    @field_validator("contributor_name", "responsible_person", "reason", "fiscal_id")
    @classmethod
    def blank_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("contributor_rif")
    @classmethod
    def validate_real_rif(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.upper().startswith("TEMP-"):
            raise ValueError("RIF temporal no permitido en registro de visita")
        return stripped

class VisitUpdateExit(SQLModel):
    exit_date: Optional[date] = None
    exit_time: Optional[time] = None
    status: Optional[VisitStatus] = None


CLOSE_STATUSES = frozenset(
    {VisitStatus.ATENDIDO, VisitStatus.INCOMPLETO, VisitStatus.REMITIDO}
)
EXIT_ALLOWED_STATUSES = frozenset(
    {
        VisitStatus.ESPERA,
        VisitStatus.EN_ATENCION,
        VisitStatus.ATENDIDO,
        VisitStatus.INCOMPLETO,
        VisitStatus.REMITIDO,
    }
)
ON_PREMISES_STATUSES = frozenset(
    {
        VisitStatus.ESPERA,
        VisitStatus.EN_ATENCION,
        VisitStatus.ATENDIDO,
        VisitStatus.INCOMPLETO,
        VisitStatus.REMITIDO,
    }
)


def format_ticket_no(entry_date: date, sequence: int) -> str:
    return f"T-{entry_date.strftime('%Y%m%d')}-{sequence:04d}"


class VisitIntake(SQLModel):
    name: str = PydanticField(..., min_length=1, max_length=255)
    reason: str = PydanticField(..., min_length=1, max_length=500)
    rif: Optional[str] = PydanticField(default=None, max_length=20)

    @field_validator("name", "reason")
    @classmethod
    def strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("campo obligatorio")
        return stripped

    @field_validator("rif")
    @classmethod
    def validate_real_rif(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.upper().startswith("TEMP-"):
            raise ValueError("RIF temporal no permitido")
        return stripped


class VisitClose(SQLModel):
    status: VisitStatus
    observations: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_close_status(cls, value: VisitStatus) -> VisitStatus:
        if value not in CLOSE_STATUSES:
            raise ValueError("status debe ser atendido, incompleto o remitido")
        return value


class VisitDayMetrics(SQLModel):
    target_date: date
    waiting: int
    in_service: int
    closed: int
    exited: int
    avg_wait_seconds: Optional[float] = None
    avg_attention_seconds: Optional[float] = None
    avg_stay_seconds: Optional[float] = None


class VisitUpdate(SQLModel):
    model_config = ConfigDict(extra="ignore")

    fiscal_id: Optional[str] = PydanticField(
        default=None,
        min_length=1,
        max_length=255,
        description="Identificador fiscal: id local o external_id",
    )
    reason: Optional[str] = PydanticField(default=None, max_length=500)
    observations: Optional[str] = Field(default=None, max_length=1000)
    received_by: Optional[str] = Field(default=None, max_length=255)
    department: Optional[str] = Field(default=None, max_length=255)
    file_number: Optional[str] = Field(default=None, max_length=100)
    entry_date: Optional[date] = None
    entry_time: Optional[time] = None
    exit_date: Optional[date] = None
    exit_time: Optional[time] = None

class VisitPublic(VisitBase):
    id: Optional[UUID] = Field(default=None)
    contributor_cedula: Optional[str] = None
    contributor_rif: Optional[str] = None
    contributor_name: Optional[str] = None
    fiscal_name: Optional[str] = None
    exit_date: Optional[date] = None
    exit_time: Optional[time] = None
    status: VisitStatus = Field(default=VisitStatus.ESPERA)
    created_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    wait_seconds: Optional[int] = None
    attention_seconds: Optional[int] = None
    stay_seconds: Optional[int] = None

    @model_validator(mode="after")
    def _set_duration_metrics(self) -> "VisitPublic":
        metrics = visit_duration_metrics(
            entry_date=self.entry_date,
            entry_time=self.entry_time,
            called_at=self.called_at,
            closed_at=self.closed_at,
            exit_at=self.exit_at,
        )
        self.wait_seconds = metrics["wait_seconds"]
        self.attention_seconds = metrics["attention_seconds"]
        self.stay_seconds = metrics["stay_seconds"]
        return self

class VisitWithPhotosPublic(VisitPublic):
    photos: list[PhotoPublic] = []

class VisitHistoryItem(SQLModel):
    id: UUID
    rif: Optional[str] = None
    contribuyente: Optional[str] = None
    registro: Optional[str] = None
    depto: Optional[str] = None
    motivo: Optional[str] = None
    estado: VisitStatus
    fiscal: Optional[str] = None

class FiscalVisitReportItem(SQLModel):
    visit_id: UUID
    fiscal_id: Optional[int] = None
    fiscal_name: Optional[str] = None
    contributor_id: int
    contributor_name: Optional[str] = None
    contributor_rif: Optional[str] = None
    entry_date: date
    entry_time: time
    exit_date: Optional[date] = None
    exit_time: Optional[time] = None
    status: VisitStatus
    reason: Optional[str] = None
    department: Optional[str] = None


class FiscalVisitsReportResponse(SQLModel):
    total: int
    skip: int
    limit: int
    items: list[FiscalVisitReportItem]


class VisitHistoryReportResponse(SQLModel):
    total: int
    skip: int
    limit: int
    items: list[VisitHistoryItem]

class Visit(VisitBase, table=True):  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    contributor_id: int = Field(foreign_key="contributor.id", index=True)
    fiscal_id: Optional[int] = Field(default=None, foreign_key="fiscals.id", index=True)
    ticket_no: Optional[str] = Field(default=None, index=True, unique=True, max_length=32)
    called_at: Optional[datetime] = Field(default=None)
    closed_at: Optional[datetime] = Field(default=None)
    exit_at: Optional[datetime] = Field(default=None)
    exit_date: Optional[date] = Field(default=None)
    exit_time: Optional[time] = Field(default=None)
    status: VisitStatus = Field(default=VisitStatus.ESPERA)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(default=None, index=True)
    
    # Relaciones
    contributor: "Contributor" = Relationship(back_populates="visits")  # noqa: F821
    fiscal: "Fiscal" = Relationship()  # noqa: F821
    photos: list["Photo"] = Relationship(back_populates="visit")  # noqa: F821
    asset_movements: list["AssetMovement"] = Relationship(back_populates="visit")  # noqa: F821