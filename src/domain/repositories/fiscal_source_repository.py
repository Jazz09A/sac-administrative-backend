from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExternalFiscalRecord:
    external_id: str
    name: str
    person_id: int | None
    email: str | None
    group_id: str | None
    supervisor_id: str | None
    status: bool


class FiscalSourceRepository(Protocol):
    async def list_active_fiscals(self) -> list[ExternalFiscalRecord]:
        """Return active fiscals from the external source."""
