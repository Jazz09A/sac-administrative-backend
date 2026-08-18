from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.core.config import Settings, get_settings
from src.core.security import OPERATOR_ROLES, CurrentUser, get_current_user, verify_token
from src.realtime.visit_ws_manager import visit_ws_manager

router = APIRouter()
CurrentOperator = Annotated[CurrentUser, Depends(get_current_user)]
AppSettings = Annotated[Settings, Depends(get_settings)]


class VisitWsTestNotificationIn(BaseModel):
    event_type: str = Field(default="visit.test")
    payload: dict[str, Any] = Field(default_factory=dict)


def _websocket_token(websocket: WebSocket) -> str:
    query_token = websocket.query_params.get("access_token")
    if query_token:
        return query_token
    authorization = websocket.headers.get("authorization") or ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token
    return ""


@router.websocket("/visits")
async def visits_dashboard_websocket(websocket: WebSocket) -> None:
    user = await verify_token(_websocket_token(websocket))
    if not user or user.role not in OPERATOR_ROLES:
        await websocket.close(code=4401)
        return

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
    settings: AppSettings,
    _: CurrentOperator,
) -> dict[str, str]:
    if not settings.is_local:
        raise HTTPException(
            status_code=403,
            detail="Endpoint disponible solo en entorno local/development",
        )

    await visit_ws_manager.publish(body.event_type, body.payload)
    return {"status": "sent", "event_type": body.event_type}
