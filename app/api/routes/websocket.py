from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError
from app.core.security import decode_access_token
from app.ws.connection_manager import manager
from uuid import UUID

router = APIRouter()

@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = decode_access_token(token)
        organization_id = UUID(payload.get("org_id"))
    except (JWTError, ValueError, TypeError):
        await websocket.close(code=1008)  # policy violation
        return

    await manager.connect(websocket, organization_id)
    try:
        while True:
            # keep the connection alive; we don't expect client messages yet,
            # but reading prevents the socket from being considered idle/dead
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, organization_id)