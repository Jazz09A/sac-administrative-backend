"""Plantillas faciales ligadas al contribuyente (cédula + RIF)."""

from datetime import datetime
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel


class FaceRegion(str, Enum):
    FULL = "full"
    PERIOCULAR = "periocular"
    NOSE = "nose"


class FaceTemplate(SQLModel, table=True):
    __tablename__ = "face_templates"

    id: int | None = Field(default=None, primary_key=True)
    contributor_id: int = Field(foreign_key="contributor.id", index=True)
    region: FaceRegion = Field(default=FaceRegion.FULL, index=True)
    pose_label: str | None = Field(default=None, max_length=64)
    glasses: bool = Field(default=False, index=True)
    embedding: bytes
    mesh_vector: bytes | None = Field(default=None)
    image_path: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    contributor: "Contributor" = Relationship(back_populates="face_templates")  # noqa: F821


class FaceTemplatePublic(SQLModel):
    id: int
    contributor_id: int
    region: FaceRegion
    pose_label: str | None = None
    glasses: bool = False
    created_at: datetime
