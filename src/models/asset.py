"""
Bienes nacionales SENIAT.

Solo patrimonio institucional de la sede (equipos, mobiliario, periféricos).
No modela pertenencias personales del contribuyente ni un interrogatorio de ingreso.
Un movimiento puede ligarse a una visita solo para trazar cuándo un bien SENIAT
salió o volvió a la sede (p. ej. un fiscal que sale con un portátil institucional).
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import Field as PydanticField
from sqlmodel import Field, Relationship, SQLModel


class AssetStatus(str, Enum):
    IN_SEDE = "in_sede"
    ASSIGNED = "assigned"
    IN_TRANSIT_OUT = "in_transit_out"


class AssetMovementDirection(str, Enum):
    OUT = "out"
    IN = "in"


class AssetMovementStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class SeniatAssetBase(SQLModel):
    inventory_code: str = PydanticField(..., min_length=1, max_length=64)
    serial: str | None = PydanticField(default=None, max_length=128)
    brand: str | None = Field(default=None, max_length=128)
    model: str | None = Field(default=None, max_length=128)
    category: str = PydanticField(..., min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    photo_object_key: str | None = Field(default=None, max_length=1000)
    workstation: str | None = Field(default=None, max_length=128)


class SeniatAsset(SeniatAssetBase, table=True):
    __tablename__ = "seniat_assets"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    inventory_code: str = Field(index=True, unique=True, max_length=64)
    serial: str | None = Field(default=None, index=True, unique=True, max_length=128)
    status: AssetStatus = Field(default=AssetStatus.IN_SEDE, index=True)
    assigned_user_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = Field(default_factory=datetime.utcnow)

    assignments: list["AssetAssignment"] = Relationship(back_populates="asset")
    movements: list["AssetMovement"] = Relationship(back_populates="asset")


class AssetAssignment(SQLModel, table=True):
    __tablename__ = "seniat_asset_assignments"

    id: int | None = Field(default=None, primary_key=True)
    asset_id: UUID = Field(foreign_key="seniat_assets.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    workstation: str | None = Field(default=None, max_length=128)
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    released_at: datetime | None = Field(default=None)

    asset: SeniatAsset = Relationship(back_populates="assignments")


class AssetMovement(SQLModel, table=True):
    __tablename__ = "seniat_asset_movements"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    asset_id: UUID = Field(foreign_key="seniat_assets.id", index=True)
    carrier_user_id: UUID = Field(foreign_key="users.id", index=True)
    visit_id: UUID | None = Field(default=None, foreign_key="visit.id", index=True)
    direction: AssetMovementDirection
    status: AssetMovementStatus = Field(default=AssetMovementStatus.OPEN, index=True)
    notes: str | None = Field(default=None, max_length=500)
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: datetime | None = Field(default=None)

    asset: SeniatAsset = Relationship(back_populates="movements")
    visit: Optional["Visit"] = Relationship(back_populates="asset_movements")  # noqa: F821


class SeniatAssetPublic(SeniatAssetBase):
    id: UUID
    status: AssetStatus
    assigned_user_id: UUID | None = None
    created_at: datetime


class AssetMovementPublic(SQLModel):
    id: UUID
    asset_id: UUID
    carrier_user_id: UUID
    visit_id: UUID | None = None
    direction: AssetMovementDirection
    status: AssetMovementStatus
    notes: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None


class SeniatAssetCreate(SQLModel):
    inventory_code: str = PydanticField(..., min_length=1, max_length=64)
    serial: str | None = PydanticField(default=None, max_length=128)
    brand: str | None = PydanticField(default=None, max_length=128)
    model: str | None = PydanticField(default=None, max_length=128)
    category: str = PydanticField(..., min_length=1, max_length=64)
    description: str | None = PydanticField(default=None, max_length=500)
    workstation: str | None = PydanticField(default=None, max_length=128)


class SeniatAssetUpdate(SQLModel):
    inventory_code: str | None = PydanticField(default=None, min_length=1, max_length=64)
    serial: str | None = PydanticField(default=None, max_length=128)
    brand: str | None = PydanticField(default=None, max_length=128)
    model: str | None = PydanticField(default=None, max_length=128)
    category: str | None = PydanticField(default=None, min_length=1, max_length=64)
    description: str | None = PydanticField(default=None, max_length=500)
    workstation: str | None = PydanticField(default=None, max_length=128)


class AssetAssignRequest(SQLModel):
    user_id: UUID
    workstation: str | None = PydanticField(default=None, max_length=128)


class AssetMovementCreate(SQLModel):
    direction: AssetMovementDirection
    carrier_user_id: UUID
    visit_id: UUID | None = None
    notes: str | None = PydanticField(default=None, max_length=500)
