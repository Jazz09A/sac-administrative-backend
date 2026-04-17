"""
Fotos evidencia por visita (MVP: 1+ por visit).
Última mod: 2026-04-17 09:01 | Changes: Init simple.
"""
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from pydantic import Field as PydanticField
from datetime import datetime
from uuid import UUID

class PhotoBase(SQLModel):
    visit_id: UUID
    photo_url: str = PydanticField(..., max_length=500)

class PhotoCreate(PhotoBase):
    pass

class PhotoPublic(PhotoBase):
    id: Optional[int] = Field(default=None)
    created_at: Optional[datetime] = None

class Photo(PhotoBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    visit_id: UUID = Field(foreign_key="visit.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relación
    visit: "Visit" = Relationship(back_populates="photos")