"""
Modelos locales para fiscales sincronizados desde MySQL.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel


class FiscalBase(SQLModel):
    external_id: str = PydanticField(..., min_length=1, max_length=64)
    name: str = PydanticField(..., min_length=1, max_length=255)
    person_id: Optional[int] = Field(default=None, index=True)
    email: Optional[str] = Field(default=None, max_length=255)
    group_id: Optional[str] = Field(default=None, max_length=64, index=True)
    supervisor_id: Optional[str] = Field(default=None, max_length=64)
    status: bool = Field(default=True, index=True)
    last_synced_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class Fiscal(FiscalBase, table=True):
    __tablename__ = "fiscals"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)


class FiscalPublic(SQLModel):
    id: int
    external_id: str
    name: str
    person_id: Optional[int] = None
    email: Optional[str] = None
    group_id: Optional[str] = None
    supervisor_id: Optional[str] = None
    status: bool


class FiscalSyncRunStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class FiscalSyncRun(SQLModel, table=True):
    __tablename__ = "fiscal_sync_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    finished_at: Optional[datetime] = None
    status: FiscalSyncRunStatus = Field(nullable=False)
    fetched_total: int = Field(default=0, nullable=False)
    inserted_total: int = Field(default=0, nullable=False)
    updated_total: int = Field(default=0, nullable=False)
    skipped_total: int = Field(default=0, nullable=False)
    error_message: Optional[str] = Field(default=None, max_length=1000)


class FiscalSyncRunPublic(SQLModel):
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: FiscalSyncRunStatus
    fetched_total: int = 0
    inserted_total: int = 0
    updated_total: int = 0
    skipped_total: int = 0
    error_message: Optional[str] = None


class FiscalSyncSummaryPublic(SQLModel):
    started_at: datetime
    finished_at: datetime
    fetched_total: int
    inserted_total: int
    updated_total: int
    skipped_total: int
    duration_ms: int
    status: FiscalSyncRunStatus
    error_message: Optional[str] = None
