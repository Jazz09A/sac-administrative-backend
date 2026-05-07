from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.core.config import Settings, get_settings

from src.realtime.visit_ws_manager import visit_ws_manager

router = APIRouter()


class VisitWsTestNotificationIn(BaseModel):
    event_type: str = Field(default="visit.test")
    payload: dict[str, Any] = Field(default_factory=dict)


@router.websocket("/visits")
async def visits_dashboard_websocket(websocket: WebSocket) -> None:
    await visit_ws_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive and detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await visit_ws_manager.disconnect(websocket)


@router.post("/visits/test-notification")
async def publish_test_visit_notification(
    body: VisitWsTestNotificationIn,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if not settings.is_local:
        raise HTTPException(
            status_code=403,
            detail="Endpoint disponible solo en entorno local/development",
        )

    await visit_ws_manager.publish(body.event_type, body.payload)
    return {"status": "sent", "event_type": body.event_type}
