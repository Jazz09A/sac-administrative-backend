"""
Visit model: ingreso/salida + status flow.
Última mod: 2026-04-17 09:01 | Changes: Status enum, relations to Contributor/Photo.
"""
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from pydantic import Field as PydanticField, field_validator
from datetime import date, datetime, time
from enum import Enum
from uuid import UUID, uuid4

from src.models.photo import PhotoPublic

class VisitStatus(str, Enum):
    """Flujo MVP."""
    ESPERA = "espera"
    ATENDIDO = "atendido"
    FINALIZADO = "finalizado"
    RECHAZADO = "rechazado"
    REPROGRAMADO = "reprogramado"

class VisitBase(SQLModel):
    contributor_id: Optional[int] = PydanticField(default=None, gt=0, description="FK interno")
    fiscal_id: Optional[int] = PydanticField(default=None, gt=0, description="FK fiscal local")
    reason: str = PydanticField(..., max_length=500)
    observations: Optional[str] = Field(default=None, max_length=1000)
    received_by: Optional[str] = Field(default=None, max_length=255)
    department: Optional[str] = Field(default=None, max_length=255)
    file_number: Optional[str] = Field(default=None, max_length=100)
    entry_date: date
    entry_time: time
    signature_image_url: Optional[str] = Field(default=None, max_length=500)

class VisitCreate(SQLModel):
    contributor_rif: str = PydanticField(
        ...,
        min_length=1,
        max_length=20,
        description="RIF fiscal del contribuyente (obligatorio; no se permiten valores temporales)",
    )
    contributor_name: str = PydanticField(..., min_length=1, max_length=255)
    fiscal_id: str = PydanticField(
        ...,
        min_length=1,
        max_length=255,
        description="Identificador fiscal: id local o external_id",
    )
    responsible_person: str = PydanticField(..., min_length=1, max_length=255)
    reason: str = PydanticField(..., max_length=500)
    observations: Optional[str] = Field(default=None, max_length=1000)
    department: Optional[str] = Field(default=None, max_length=255)
    file_number: Optional[str] = Field(default=None, max_length=100)
    entry_date: date
    entry_time: time
    signature_image_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("contributor_rif")
    @classmethod
    def validate_real_rif(cls, v: str) -> str:
        s = v.strip()
        if s.upper().startswith("TEMP-"):
            raise ValueError("RIF temporal no permitido en registro de visita")
        return s

class VisitUpdateExit(SQLModel):
    exit_date: Optional[date] = None
    exit_time: Optional[time] = None
    status: Optional[VisitStatus] = None

class VisitPublic(VisitBase):
    id: Optional[UUID] = Field(default=None)
    fiscal_name: Optional[str] = None
    exit_date: Optional[date] = None
    exit_time: Optional[time] = None
    status: VisitStatus = Field(default=VisitStatus.ESPERA)
    created_at: Optional[datetime] = None

class VisitWithPhotosPublic(VisitPublic):
    photos: List[PhotoPublic] = []

class VisitHistoryItem(SQLModel):
    id: UUID
    rif: str
    contribuyente: str
    registro: Optional[str] = None
    depto: Optional[str] = None
    motivo: str
    estado: VisitStatus
    fiscal: Optional[str] = None

class FiscalVisitReportItem(SQLModel):
    visit_id: UUID
    fiscal_id: Optional[int] = None
    fiscal_name: Optional[str] = None
    contributor_id: int
    contributor_name: str
    contributor_rif: str
    entry_date: date
    entry_time: time
    exit_date: Optional[date] = None
    exit_time: Optional[time] = None
    status: VisitStatus
    reason: str
    department: Optional[str] = None


class FiscalVisitsReportResponse(SQLModel):
    total: int
    items: list[FiscalVisitReportItem]

class Visit(VisitBase, table=True):  # type: ignore
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    contributor_id: int = Field(foreign_key="contributor.id", index=True)
    fiscal_id: Optional[int] = Field(default=None, foreign_key="fiscals.id", index=True)
    exit_date: Optional[date] = Field(default=None)
    exit_time: Optional[time] = Field(default=None)
    status: VisitStatus = Field(default=VisitStatus.ESPERA)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    # Relaciones
    contributor: "Contributor" = Relationship(back_populates="visits")
    fiscal: "Fiscal" = Relationship()
    photos: List["Photo"] = Relationship(back_populates="visit")