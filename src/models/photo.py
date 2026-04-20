"""
Fotos evidencia por visita (MVP: 1+ por visit).
Última mod: 2026-04-20 | Changes: photo_url → object_key + metadata (bucket, content_type, etc.).
"""
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from pydantic import Field as PydanticField
from datetime import datetime
from uuid import UUID


class PhotoBase(SQLModel):
    visit_id: UUID
    object_key: str = PydanticField(..., max_length=1000)
    bucket: Optional[str] = Field(default=None, max_length=255)
    content_type: Optional[str] = Field(default=None, max_length=127)
    original_filename: Optional[str] = Field(default=None, max_length=500)
    size: Optional[int] = Field(default=None)


class PhotoCreate(PhotoBase):
    pass


class PhotoPublic(PhotoBase):
    id: Optional[int] = Field(default=None)
    created_at: Optional[datetime] = None
    # URL pública lista para usar: R2_PUBLIC_BASE_URL + "/" + object_key
    # Poblada por la capa de API; no se almacena en BD.
    photo_url: Optional[str] = Field(default=None)


class Photo(PhotoBase, table=True):  # type: ignore
    id: Optional[int] = Field(default=None, primary_key=True)
    visit_id: UUID = Field(foreign_key="visit.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relación
    visit: "Visit" = Relationship(back_populates="photos")
