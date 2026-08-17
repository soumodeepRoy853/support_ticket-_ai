import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.ws.connection_manager import redis_listener

from app.api.routes import auth, ticket, websocket, analytics

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(redis_listener())
    yield
    task.cancel()

app = FastAPI(title="Smart Support Ticket System", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(ticket.router)
app.include_router(websocket.router)
app.include_router(analytics.router)

@app.get("/")
async def root():
    return {
        "message": "Smart Support Ticket API is running",
        "status": "ok",
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}