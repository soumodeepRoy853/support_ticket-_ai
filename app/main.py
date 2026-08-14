from fastapi import FastAPI

app = FastAPI(title="Smart Support Ticket System", version="0.1.0")

@app.get("/")
async def root():
    return {
        "message": "Smart Support Ticket API is running",
        "status": "ok",
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}