from __future__ import annotations

from asyncio import Lock
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder


class VisitWebSocketManager:
    """Manage active visit dashboard websocket connections."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def publish(self, event_type: str, payload: Any) -> None:
        message = {
            "type": event_type,
            "occurred_at": datetime.now(UTC).isoformat(),
            "payload": jsonable_encoder(payload),
        }

        async with self._lock:
            targets = list(self._connections)

        stale_connections: list[WebSocket] = []
        for connection in targets:
            try:
                await connection.send_json(message)
            except Exception:
                stale_connections.append(connection)

        if stale_connections:
            async with self._lock:
                for connection in stale_connections:
                    self._connections.discard(connection)


visit_ws_manager = VisitWebSocketManager()
