"""
SQLModel + Pydantic para Contributor.
Última mod: 2026-04-17 09:01 | Changes: Init from MVP proposal (rif unique).
"""
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from pydantic import Field as PydanticField
from datetime import datetime
from enum import Enum

class ContributorType(str, Enum):
    """Tipos desde propuesta."""
    NATURAL = "persona natural"
    JURIDICA = "juridica"
    REPRESENTANTE = "representante"
    GESTOR = "gestor"

class ContributorBase(SQLModel):
    rif: str = PydanticField(..., min_length=1, max_length=20, description="RIF único obligatorio")
    name: str = PydanticField(..., max_length=255)
    type: ContributorType
    occupation: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)

class ContributorCreate(ContributorBase):
    pass

class ContributorUpdate(SQLModel):
    name: Optional[str] = Field(default=None, max_length=255)
    type: Optional[ContributorType] = None
    occupation: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)

class ContributorPublic(ContributorBase):
    id: Optional[int] = Field(default=None)
    created_at: Optional[datetime] = None

class Contributor(ContributorBase, table=True):  # type: ignore
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    # Relaciones
    visits: list["Visit"] = Relationship(back_populates="contributor")