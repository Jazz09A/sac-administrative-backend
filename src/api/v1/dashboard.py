"""
Dashboard endpoints avanzados.
Última mod: 2026-04-17 09:47 | Changes: advanced_summary con todos métricos.
"""
from datetime import date
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import require_operator
from src.crud.dashboard import get_advanced_dashboard

router = APIRouter(dependencies=[Depends(require_operator)])

@router.get("/advanced", response_model=Dict[str, Any])
async def dashboard_advanced(
    target_date: date | None = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Dashboard completo: curso, %vs ayer/prev, últimas 5."""
    return await get_advanced_dashboard(db, target_date)