from fastapi import FastAPI
from app.api.routes import auth, ticket

app = FastAPI(title="Smart Support Ticket System", version="0.1.0")

app.include_router(auth.router)
app.include_router(ticket.router)

@app.get("/")
async def root():
    return {
        "message": "Smart Support Ticket API is running",
        "status": "ok",
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}