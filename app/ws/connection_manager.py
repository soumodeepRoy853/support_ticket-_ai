from fastapi import WebSocket
from uuid import UUID
import json
import logging
import redis.asyncio as aioredis
from app.core.config import settings
import asyncio

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # org_id -> list of active websocket connections
        self.active_connections: dict[UUID, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, organization_id: UUID):
        await websocket.accept()
        self.active_connections.setdefault(organization_id, []).append(websocket)
        logger.info(f"WebSocket connected for org {organization_id}. Total: {len(self.active_connections[organization_id])}")

    def disconnect(self, websocket: WebSocket, organization_id: UUID):
        if organization_id in self.active_connections:
            self.active_connections[organization_id].remove(websocket)
            if not self.active_connections[organization_id]:
                del self.active_connections[organization_id]


    async def broadcast_to_org(self, organization_id: UUID, message: dict):
        connections = self.active_connections.get(organization_id, [])
        dead_connections = []

        for connection in connections:
            try:
                await connection.send_text(json.dumps(message, default=str))
            except Exception:
                dead_connections.append(connection)

        # clean up connections that failed (client disconnected without a clean close)
        for dead in dead_connections:
            self.disconnect(dead, organization_id)


manager = ConnectionManager()


async def redis_listener():
    """Runs inside the FastAPI process. Listens for events published by Celery workers
    and re-broadcasts them to connected WebSocket clients."""
    redis_client = aioredis.from_url(settings.redis_url)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("ticket_events")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            organization_id = UUID(data["organization_id"])
            await manager.broadcast_to_org(organization_id, data["payload"])
        except Exception as e:
            logger.error(f"Failed to process redis pubsub message: {e}")