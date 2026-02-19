from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes_tasks import router as tasks_router

import uvicorn

from app.api.routes_ai import router as ai_router
from app.api.routes_settings import router as settings_router

# ✅ NEW
from app.database.init_db import init_db

from app.scheduler.reminder_scheduler import ReminderScheduler
import threading




@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 AI Life Assistant Backend Starting...")

    # ✅ Initialize database
    init_db()

    scheduler = ReminderScheduler()
    threading.Thread(target=scheduler.start, daemon=True).start()

    yield

    print("🛑 AI Life Assistant Backend Shutting Down...")


app = FastAPI(
    title="AI Life Assistant Backend",
    description="Backend API for Jarvis-Style Personal AI System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "AI Life Assistant Backend Running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Routers
app.include_router(ai_router, prefix="/api/ai", tags=["AI"])
app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])
app.include_router(tasks_router, prefix="/api/tasks", tags=["Tasks"])



if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
