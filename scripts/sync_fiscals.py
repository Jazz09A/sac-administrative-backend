"""
Sincroniza fiscales desde MySQL (fuente) hacia Postgres (destino)
con modo interactivo para revisar faltantes.

Uso:
    uv run python scripts/sync_fiscals.py
"""
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from sqlmodel import select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.database import get_session
from src.core.mysql_database import get_mysql_session
from src.infrastructure.mysql.fiscal_source_mysql_repository import MySQLFiscalSourceRepository
from src.infrastructure.postgres.fiscal_postgres_repository import PostgresFiscalRepository
from src.infrastructure.postgres.fiscal_sync_run_postgres_repository import (
    PostgresFiscalSyncRunRepository,
)
from src.models.fiscal import Fiscal
from src.services.fiscal_sync_service import FiscalSyncService


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _to_payload(row: Any) -> dict[str, Any]:
    return {
        "external_id": row.external_id,
        "name": row.name,
        "person_id": row.person_id,
        "email": row.email,
        "group_id": row.group_id,
        "supervisor_id": row.supervisor_id,
        "status": row.status,
    }


def _print_header(total_mysql: int, total_pg: int, total_missing: int) -> None:
    print("\n===== RESUMEN ACTUAL =====")
    print(f"MySQL activos: {total_mysql}")
    print(f"Postgres encontrados: {total_pg}")
    print(f"Faltantes por cargar: {total_missing}")
    print("==========================\n")


def _print_item(index: int, total: int, item: dict[str, Any]) -> None:
    print(f"\n[{index + 1}/{total}] Fiscal pendiente")
    print(f"  external_id : {item['external_id']}")
    print(f"  name        : {item['name']}")
    print(f"  person_id   : {item['person_id']}")
    print(f"  email       : {item['email']}")
    print(f"  group_id    : {item['group_id']}")
    print(f"  supervisor  : {item['supervisor_id']}")
    print(f"  status      : {item['status']}")


def _print_help() -> None:
    print(
        """
Comandos:
  n  -> siguiente pendiente
  p  -> pendiente anterior
  i  -> insertar pendiente actual
  a  -> insertar todos los pendientes
  l  -> listar pendientes (resumido)
  d  -> mostrar detalle del actual
  e  -> exportar pendientes a JSON
  r  -> refrescar comparacion MySQL vs Postgres
  s  -> ejecutar sync global (servicio actual)
  q  -> salir
""".strip()
    )


async def _build_missing_list(source_repo: MySQLFiscalSourceRepository, pg_session: Any) -> tuple[list[dict[str, Any]], int, int]:
    external_rows = await source_repo.list_active_fiscals()
    mysql_fiscals_by_external_id = {row.external_id: row for row in external_rows}
    mysql_external_ids = list(mysql_fiscals_by_external_id.keys())

    postgres_external_ids: set[str] = set()
    if mysql_external_ids:
        existing_result = await pg_session.execute(
            select(Fiscal.external_id).where(Fiscal.external_id.in_(mysql_external_ids))
        )
        postgres_external_ids = set(existing_result.scalars().all())

    missing_external_ids = sorted(set(mysql_external_ids) - postgres_external_ids)
    missing_fiscals = [
        _to_payload(mysql_fiscals_by_external_id[external_id]) for external_id in missing_external_ids
    ]
    return missing_fiscals, len(mysql_external_ids), len(postgres_external_ids)


async def run_sync() -> int:
    async with get_session() as pg_session:
        async with get_mysql_session() as mysql_session:
            source_repo = MySQLFiscalSourceRepository(mysql_session)
            fiscal_repo = PostgresFiscalRepository(pg_session)
            sync_run_repo = PostgresFiscalSyncRunRepository(pg_session)
            service = FiscalSyncService(source_repo, fiscal_repo, sync_run_repo)

            missing_fiscals, total_mysql, total_pg = await _build_missing_list(source_repo, pg_session)
            current_index = 0
            _print_header(total_mysql, total_pg, len(missing_fiscals))
            _print_help()

            if missing_fiscals:
                _print_item(current_index, len(missing_fiscals), missing_fiscals[current_index])
            else:
                print("No hay faltantes en este momento.")

            while True:
                cmd = input("\nComando> ").strip().lower()

                if cmd == "q":
                    print("Saliendo sin ejecutar acciones adicionales.")
                    return 0

                if cmd == "h" or cmd == "help":
                    _print_help()
                    continue

                if cmd == "l":
                    if not missing_fiscals:
                        print("No hay pendientes.")
                        continue
                    print("\nPendientes:")
                    for idx, item in enumerate(missing_fiscals, start=1):
                        print(f"  {idx}. {item['external_id']} | {item['name']} | {item['email']}")
                    continue

                if cmd == "d":
                    if not missing_fiscals:
                        print("No hay pendientes.")
                        continue
                    _print_item(current_index, len(missing_fiscals), missing_fiscals[current_index])
                    continue

                if cmd == "n":
                    if not missing_fiscals:
                        print("No hay pendientes.")
                        continue
                    current_index = (current_index + 1) % len(missing_fiscals)
                    _print_item(current_index, len(missing_fiscals), missing_fiscals[current_index])
                    continue

                if cmd == "p":
                    if not missing_fiscals:
                        print("No hay pendientes.")
                        continue
                    current_index = (current_index - 1) % len(missing_fiscals)
                    _print_item(current_index, len(missing_fiscals), missing_fiscals[current_index])
                    continue

                if cmd == "e":
                    export_path = PROJECT_ROOT / "missing_fiscals.json"
                    export_path.write_text(
                        json.dumps(
                            {
                                "missing_in_postgres_total": len(missing_fiscals),
                                "missing_fiscals": missing_fiscals,
                            },
                            ensure_ascii=True,
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                    print(f"Pendientes exportados en: {export_path}")
                    continue

                if cmd == "i":
                    if not missing_fiscals:
                        print("No hay pendientes.")
                        continue
                    current = missing_fiscals[current_index]
                    try:
                        inserted, updated = await fiscal_repo.upsert_many([current])
                        await pg_session.commit()
                        print(
                            f"Registro procesado external_id={current['external_id']} "
                            f"(inserted={inserted}, updated={updated})"
                        )
                        missing_fiscals.pop(current_index)
                        if missing_fiscals:
                            current_index = min(current_index, len(missing_fiscals) - 1)
                            _print_item(current_index, len(missing_fiscals), missing_fiscals[current_index])
                        else:
                            print("Ya no quedan pendientes.")
                    except Exception as exc:
                        await pg_session.rollback()
                        print(f"Error insertando {current['external_id']}: {exc}")
                    continue

                if cmd == "a":
                    if not missing_fiscals:
                        print("No hay pendientes.")
                        continue
                    processed = 0
                    failed = 0
                    for item in list(missing_fiscals):
                        try:
                            inserted, updated = await fiscal_repo.upsert_many([item])
                            await pg_session.commit()
                            if inserted or updated:
                                processed += 1
                            missing_fiscals.remove(item)
                        except Exception as exc:
                            failed += 1
                            await pg_session.rollback()
                            print(f"Error insertando {item['external_id']}: {exc}")
                    print(f"Carga masiva terminada. procesados={processed}, fallidos={failed}")
                    if missing_fiscals:
                        current_index = min(current_index, len(missing_fiscals) - 1)
                    continue

                if cmd == "r":
                    missing_fiscals, total_mysql, total_pg = await _build_missing_list(
                        source_repo, pg_session
                    )
                    current_index = 0
                    _print_header(total_mysql, total_pg, len(missing_fiscals))
                    if missing_fiscals:
                        _print_item(current_index, len(missing_fiscals), missing_fiscals[current_index])
                    else:
                        print("No hay faltantes en este momento.")
                    continue

                if cmd == "s":
                    summary = await service.sync()
                    print("\nResultado sync global:")
                    print(json.dumps(summary.to_dict(), ensure_ascii=True, indent=2))
                    if summary.status == "failed":
                        return 1
                    missing_fiscals, total_mysql, total_pg = await _build_missing_list(
                        source_repo, pg_session
                    )
                    current_index = 0
                    _print_header(total_mysql, total_pg, len(missing_fiscals))
                    continue

                print("Comando no valido. Usa 'h' para ayuda.")


def main() -> int:
    try:
        return asyncio.run(run_sync())
    except KeyboardInterrupt:
        print("Sincronizacion cancelada por el usuario.", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover
        print(f"Error ejecutando sincronizacion: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
