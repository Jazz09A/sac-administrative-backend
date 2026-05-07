"""
Smoke test realtime notifications for visit websocket channel.

Usage:
    uv run python scripts/test_ws_notification.py
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
from datetime import UTC, datetime
from typing import Any

import httpx
import websockets


def _to_ws_url(http_base_url: str) -> str:
    base = http_base_url.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base.removeprefix("https://")
    if base.startswith("http://"):
        return "ws://" + base.removeprefix("http://")
    raise ValueError("base-url debe iniciar con http:// o https://")


async def _trigger_notification(
    api_base_url: str,
    event_type: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> httpx.Response:
    endpoint = f"{api_base_url.rstrip('/')}/api/v1/ws/visits/test-notification"
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        return await client.post(
            endpoint,
            json={
                "event_type": event_type,
                "payload": payload,
            },
        )


async def run(args: argparse.Namespace) -> int:
    api_base_url = args.base_url.rstrip("/")
    ws_url = f"{_to_ws_url(api_base_url)}/api/v1/ws/visits"

    now_iso = datetime.now(UTC).isoformat()
    payload = {
        "id": "49a5f2a5-889f-4739-bf38-b295d2df07ef",
        "contributor_name": "Comercial ABC, C.A.",
        "fiscal_id": 7,
        "fiscal_name": "Fiscal Demo",
        "reason": "Evento simulado desde script",
        "observations": "Prueba realtime frontend",
        "received_by": "Sistema",
        "department": "Fiscalizacion",
        "file_number": "EXP-TEST-WS-001",
        "entry_date": "2026-05-05",
        "entry_time": "13:36:00",
        "signature_image_url": "https://assets.sac-app.com/sac-administrative/sac-visits/demo/photo.png",
        "exit_date": None,
        "exit_time": None,
        "status": "espera",
        "created_at": now_iso,
        "deleted_at": None,
        "photos": [
            {
                "visit_id": "49a5f2a5-889f-4739-bf38-b295d2df07ef",
                "object_key": "sac-administrative/sac-visits/demo/photo.png",
                "bucket": "sac-visits-prov",
                "content_type": "image/png",
                "original_filename": "photo.png",
                "size": 12345,
                "id": 1,
                "created_at": now_iso,
                "photo_url": "https://assets.sac-app.com/sac-administrative/sac-visits/demo/photo.png",
            }
        ],
    }

    print(f"Connecting websocket client: {ws_url}")
    async with websockets.connect(ws_url) as socket:
        print("Triggering backend notification...")
        response = await _trigger_notification(
            api_base_url=api_base_url,
            event_type=args.event_type,
            payload=payload,
            timeout_seconds=args.timeout,
        )

        if response.status_code == 403:
            print("ERROR: endpoint devolvio 403 Forbidden.")
            print(
                "Este endpoint de prueba solo funciona en entorno local/development "
                "(ENVIRONMENT=local o ENVIRONMENT=development)."
            )
            return 2

        if response.status_code != 200:
            print(f"ERROR: status inesperado {response.status_code}")
            print(response.text)
            return 3

        try:
            raw_message = await asyncio.wait_for(socket.recv(), timeout=args.timeout)
        except TimeoutError:
            print(
                "ERROR: timeout esperando evento WS. "
                "Verifica que el backend publique en /api/v1/ws/visits "
                "y que no haya filtros de tipo en el frontend."
            )
            return 5

    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8")
    event = json.loads(raw_message)
    print("Notification received on websocket:")
    print(json.dumps(event, indent=2, ensure_ascii=False))

    if event.get("type") != args.event_type:
        print(
            "ERROR: tipo de evento inesperado. "
            f"Esperado={args.event_type} Recibido={event.get('type')}"
        )
        return 4

    print("OK: realtime funcionando, el cliente recibio la notificacion.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Realtime websocket smoke test")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--event-type",
        default="visit.created",
        help="Tipo de evento a publicar (default: visit.created)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=8.0,
        help="Timeout en segundos para HTTP/WS (default: 8)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
