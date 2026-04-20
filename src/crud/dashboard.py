"""
Dashboard avanzado MVP.
Última mod: 2026-04-17 09:47 | Changes: +vs ayer, % hora anterior, últimas 5.
"""
from typing import Dict, Any
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, extract
from sqlmodel import select
from src.models.visit import Visit, VisitStatus
from src.models.contributor import Contributor
from typing import Optional
async def get_advanced_dashboard(session: AsyncSession, target_date: Optional[date] = None) -> Dict[str, Any]:
    """Dashboard completo requerido."""
    if target_date is None:
        target_date = date.today()
    
    yesterday = target_date - timedelta(days=1)
    
    # Base queries
    today_filter = Visit.entry_date == target_date
    yesterday_filter = Visit.entry_date == yesterday
    
    # 1. Visitas en curso (status espera/atendido sin salida)
    en_curso = select(func.count()).where(
        today_filter,
        Visit.status.in_([VisitStatus.ESPERA, VisitStatus.ATENDIDO]),
        Visit.exit_date.is_(None)
    )
    
    # 2. Entradas hoy vs ayer (%)
    today_entries = select(func.count()).where(today_filter)
    yesterday_entries = select(func.count()).where(yesterday_filter)
    hoy_total = (await session.execute(today_entries)).scalar() or 0
    ayer_total = (await session.execute(yesterday_entries)).scalar() or 0
    entradas_vs_ayer = {
        "hoy": hoy_total,
        "ayer": ayer_total,
        "porcentaje_cambio": ((hoy_total - ayer_total) / ayer_total * 100) if ayer_total else 100
    }
    
    # 3. Personas dentro % vs hora anterior (asumir hora actual)
    now_hour = func.extract('hour', func.now())
    prev_hour = now_hour - 1
    dentro_actual = select(func.count()).where(
        today_filter,
        Visit.status.in_([VisitStatus.ESPERA, VisitStatus.ATENDIDO]),
        Visit.exit_date.is_(None),
        extract('hour', Visit.entry_time) <= now_hour
    )
    dentro_prev = select(func.count()).where(
        today_filter,
        Visit.status.in_([VisitStatus.ESPERA, VisitStatus.ATENDIDO]),
        Visit.exit_date.is_(None),
        extract('hour', Visit.entry_time) <= prev_hour
    )
    dentro_hoy = (await session.execute(dentro_actual)).scalar() or 0
    dentro_prev_hora = (await session.execute(dentro_prev)).scalar() or 0
    dentro_vs_prev = {
        "actual": dentro_hoy,
        "hora_anterior": dentro_prev_hora,
        "porcentaje_cambio": ((dentro_hoy - dentro_prev_hora) / dentro_prev_hora * 100) if dentro_prev_hora else 100
    }
    
    # 4-5. Visitas atendidas/pendientes hoy
    # visitas_atendidas = TOTAL de visitas del día (todas las que ingresaron hoy)
    # visitas_pendientes = las que aún están en espera
    atendidas = select(func.count()).where(today_filter)
    pendientes = select(func.count()).where(today_filter, Visit.status == VisitStatus.ESPERA)
    
    # 6. Últimas 5 visitas (recientes hoy)
    ultimas = select(Visit, Contributor).join(Contributor).where(
        today_filter
    ).order_by(Visit.created_at.desc()).limit(5)
    
    result = {
        "date": target_date.isoformat(),
        "visitas_en_curso": (await session.execute(en_curso)).scalar() or 0,
        "entradas_dia": entradas_vs_ayer,
        "personas_dentro": dentro_vs_prev,
        "visitas_atendidas": (await session.execute(atendidas)).scalar() or 0,
        "visitas_pendientes": (await session.execute(pendientes)).scalar() or 0,
        "ultimas_actividades": []
    }
    
    # Populate últimas
    ultimas_result = await session.execute(ultimas)
    for visit, contrib in ultimas_result.all():
        result["ultimas_actividades"].append({
            "id": str(visit.id),
            "motivo": visit.reason[:100],
            "contribuyente": contrib.name,
            "rif": contrib.rif,
            "responsable": visit.received_by,
            "status": visit.status,
            "entry_time": visit.entry_time.strftime("%H:%M")
        })
    
    return result