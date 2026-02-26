from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import uvicorn
import threading
import base64
import json
import os

# ROUTERS
from app.api.routes_tasks import router as tasks_router
from app.api.routes_ai import router as ai_router
from app.api.routes_settings import router as settings_router
from app.api.routes_setup import router as setup_router

# CORE
from app.database.init_db import init_db
from app.scheduler.reminder_scheduler import ReminderScheduler

# SERVICES
from app.agents.gmail_agent import GmailAgent
from app.notifications.email_notifier import EmailNotifier
from app.voice.voice_assistant import VoiceAssistant

from app.api.routes_auth import router as auth_router

from app.api.voice import router as voice_router
from app.api.routes_rag import router as rag_router

# -------------------------
# GLOBAL SERVICES
# -------------------------
voice_assistant = VoiceAssistant()

# GmailAgent created per user dynamically
notifier = EmailNotifier(
    gmail_agent=None,
    voice_assistant=voice_assistant,
    ai_url="http://127.0.0.1:8000/api/ai/chat"
)


# -------------------------
# LIFESPAN
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):

    print("🚀 AI Life Assistant Backend Starting...")

    # Initialize DB
    init_db()

    # Start background scheduler
    scheduler = ReminderScheduler()
    threading.Thread(target=scheduler.start, daemon=True).start()

    yield

    print("🛑 AI Life Assistant Backend Shutting Down...")


# -------------------------
# APP
# -------------------------
app = FastAPI(
    title="AI Life Assistant Backend",
    description="Backend API for Jarvis-Style Personal AI System",
    version="0.1.0",
    lifespan=lifespan,
)


# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "*"  # Allow Electron origins
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# ROOT
# -------------------------
@app.get("/")
async def root():
    return {"message": "AI Life Assistant Backend Running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# -------------------------
# GMAIL PUBSUB WEBHOOK (MULTI USER)
# -------------------------
@app.post("/gmail/webhook")
async def gmail_webhook(request: Request):

    body = await request.json()

    message = body.get("message", {})
    data = message.get("data")

    if not data:
        return {"status": "no data"}

    decoded = base64.b64decode(data).decode("utf-8")
    payload = json.loads(decoded)

    history_id = payload.get("historyId")

    print("📧 Gmail event received:", history_id)

    # -------------------------
    # FIND USER FROM MAPPING
    # -------------------------
    users_file = os.path.join("app", "data", "pubsub_users.json")

    if not os.path.exists(users_file):
        return {"status": "no user mapping"}

    with open(users_file, "r") as f:
        users = json.load(f)

    user_id = None

    for uid, info in users.items():
        if str(info.get("historyId")) == str(history_id):
            user_id = uid
            break

    if not user_id:
        print("⚠️ User not found for historyId")
        return {"status": "user not found"}

    print(f"✅ Routed to user: {user_id}")

    # -------------------------
    # LOAD USER GMAIL
    # -------------------------
    gmail_agent = GmailAgent(user_id=user_id)

    results = gmail_agent.service.users().messages().list(
        userId="me",
        maxResults=1
    ).execute()

    msgs = results.get("messages", [])

    if msgs:
        msg_id = msgs[0]["id"]

        notifier.gmail_agent = gmail_agent
        notifier.notify_new_email(msg_id)

    return {"status": "ok"}


# -------------------------
# ROUTERS
# -------------------------
app.include_router(setup_router, prefix="/api/setup", tags=["Setup"])
app.include_router(ai_router, prefix="/api/ai", tags=["AI"])
app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])
app.include_router(tasks_router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(voice_router, prefix="/api")
app.include_router(rag_router, prefix="/api/rag", tags=["RAG"])


# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
