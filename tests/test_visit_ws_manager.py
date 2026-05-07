import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.realtime.visit_ws_manager import VisitWebSocketManager


class FakeWebSocket:
    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.fail_on_send = fail_on_send
        self.accepted = False
        self.messages: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        if self.fail_on_send:
            raise RuntimeError("simulated websocket send failure")
        self.messages.append(message)


@pytest.mark.asyncio
async def test_visit_ws_manager_publish_delivers_event_payload() -> None:
    manager = VisitWebSocketManager()
    websocket = FakeWebSocket()
    payload = {"id": "49a5f2a5-889f-4739-bf38-b295d2df07ef", "status": "espera"}

    await manager.connect(websocket)  # type: ignore[arg-type]
    await manager.publish("visit.created", payload)
    await manager.disconnect(websocket)  # type: ignore[arg-type]

    assert websocket.accepted is True
    assert len(websocket.messages) == 1

    event = websocket.messages[0]
    assert event["type"] == "visit.created"
    assert event["payload"] == payload
    # Verifica formato ISO UTC sin fijar fecha/hora exacta.
    assert isinstance(event["occurred_at"], str)
    datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_visit_ws_manager_removes_stale_connections() -> None:
    manager = VisitWebSocketManager()
    healthy_websocket = FakeWebSocket()
    failing_websocket = FakeWebSocket(fail_on_send=True)

    await manager.connect(healthy_websocket)  # type: ignore[arg-type]
    await manager.connect(failing_websocket)  # type: ignore[arg-type]

    await manager.publish("visit.updated", {"id": "abc"})
    await manager.publish("visit.updated", {"id": "def"})

    # El websocket fallido se elimina tras el primer publish.
    assert len(healthy_websocket.messages) == 2
    assert healthy_websocket.messages[0]["payload"] == {"id": "abc"}
    assert healthy_websocket.messages[1]["payload"] == {"id": "def"}
