"""
SQLModel + Pydantic para Contributor.
Última mod: 2026-04-17 09:01 | Changes: Init from MVP proposal (rif unique).
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field as PydanticField
from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel


class ContributorType(str, Enum):
    """Tipos desde propuesta."""
    NATURAL = "persona natural"
    JURIDICA = "juridica"
    REPRESENTANTE = "representante"
    GESTOR = "gestor"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _reject_temp_rif(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is not None and normalized.upper().startswith("TEMP-"):
        raise ValueError("RIF temporal no permitido")
    return normalized

class ContributorBase(SQLModel):
    rif: Optional[str] = PydanticField(
        default=None,
        max_length=20,
        description="RIF único opcional; PostgreSQL permite varios NULL",
    )
    cedula: Optional[str] = PydanticField(
        default=None,
        max_length=20,
        description="Cédula de identidad; une biometría y ficha del contribuyente",
    )
    name: Optional[str] = PydanticField(default=None, max_length=255)
    type: ContributorType
    occupation: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("rif")
    @classmethod
    def validate_rif(cls, value: str | None) -> str | None:
        return _reject_temp_rif(value)

    @field_validator("name", "cedula")
    @classmethod
    def blank_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

class ContributorCreate(ContributorBase):
    pass

class ContributorUpdate(SQLModel):
    name: Optional[str] = Field(default=None, max_length=255)
    type: Optional[ContributorType] = None
    rif: Optional[str] = Field(default=None, max_length=20)
    cedula: Optional[str] = Field(default=None, max_length=20)
    occupation: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("rif")
    @classmethod
    def validate_rif(cls, value: str | None) -> str | None:
        return _reject_temp_rif(value)

    @field_validator("name", "cedula")
    @classmethod
    def blank_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

class ContributorPublic(ContributorBase):
    id: Optional[int] = Field(default=None)
    created_at: Optional[datetime] = None

class ContributorSearchResponse(ContributorPublic):
    last_fiscal_id: Optional[int] = None
    last_reason: Optional[str] = None

class Contributor(ContributorBase, table=True):  # type: ignore
    id: Optional[int] = Field(default=None, primary_key=True)
    # unique permite varios NULL; create_all no ALTER — recrear Postgres si rif/name eran NOT NULL.
    rif: Optional[str] = Field(default=None, index=True, unique=True, max_length=20)
    cedula: Optional[str] = Field(default=None, index=True, unique=True, max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    # Relaciones
    visits: list["Visit"] = Relationship(back_populates="contributor")  # noqa: F821
    face_templates: list["FaceTemplate"] = Relationship(back_populates="contributor")  # noqa: F821