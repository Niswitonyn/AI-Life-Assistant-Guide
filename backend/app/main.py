from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from starlette.responses import JSONResponse

import uvicorn
import threading
import base64
import json
import logging
import time
from app.config.paths import USERS_FILE

# ROUTERS
from app.api.routes_tasks import router as tasks_router
from app.api.routes_ai import router as ai_router
from app.api.routes_settings import router as settings_router
from app.api.routes_setup import router as setup_router

# CORE
from app.database.init_db import init_db
from app.scheduler.reminder_scheduler import ReminderScheduler
from app.memory.memory_cleanup import MemoryCleanupScheduler

# SERVICES
from app.agents.gmail_agent import GmailAgent
from app.notifications.email_notifier import EmailNotifier
from app.voice.voice_assistant import VoiceAssistant
from app.services.email_monitor import create_email_monitor

from app.api.routes_auth import router as auth_router
from app.api.routes_user import router as user_router

from app.api.voice import router as voice_router
from app.api.routes_voice import router as voice_input_router
from app.api.routes_rag import router as rag_router
from app.api.routes_gsuite import router as gsuite_router
from app.api.routes_events import router as events_router
from app.api.routes_memory import router as memory_router
from app.security.rate_limiter import rate_limiter
from app.security.security_logs import log_security_event
from app.api.routes_documents import router as documents_router
from app.api.routes_learning import router as learning_router
from app.api.routes_system import router as system_router
from app.monitoring.performance_metrics import performance_metrics

# -------------------------
# GLOBAL SERVICES
# -------------------------
logger = logging.getLogger(__name__)

voice_assistant = None
try:
    voice_assistant = VoiceAssistant()
    logger.info("Voice assistant initialized")
except Exception as exc:
    logger.warning(f"Voice assistant init failed (non-critical): {exc}")

# GmailAgent created per user dynamically
notifier = EmailNotifier(
    gmail_agent=None,
    voice_assistant=voice_assistant if voice_assistant else None,
    ai_url="http://127.0.0.1:8000/api/ai/chat"
)
email_monitor = create_email_monitor(notifier)


# -------------------------
# LIFESPAN
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):

    print("AI Life Assistant Backend Starting...")

    # Initialize DB
    init_db()

    # Start background scheduler
    scheduler = ReminderScheduler()
    threading.Thread(target=scheduler.start, daemon=True).start()

    memory_scheduler = MemoryCleanupScheduler()
    threading.Thread(target=memory_scheduler.start, daemon=True).start()

    # Start inbox monitoring (poll tracked senders)
    try:
        email_monitor.start()
    except Exception as exc:
        logger.warning(f"Email monitor start failed (non-critical): {exc}")

    # Start system health monitor
    try:
        from app.monitoring.health_monitor import health_monitor

        await health_monitor.start()
    except Exception as exc:
        logger.warning(f"Health monitor start failed (non-critical): {exc}")

    yield

    print("AI Life Assistant Backend Shutting Down...")

    try:
        from app.monitoring.health_monitor import health_monitor

        await health_monitor.stop()
    except Exception:
        pass


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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# BASIC RATE LIMITING (in-memory)
# -------------------------
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path or ""
    ip = (request.client.host if request.client else "") or "unknown"

    # Conservative defaults; adjust via env by editing this mapping.
    rules = [
        ("/api/ai/chat", 60, 60.0),
        ("/api/voice/input", 30, 60.0),
        ("/voice/input", 30, 60.0),
        ("/api/documents/upload", 10, 60.0),
        ("/documents/upload", 10, 60.0),
    ]

    for prefix, limit, window_s in rules:
        if path.startswith(prefix):
            ok = rate_limiter.allow(ip, prefix, limit=limit, window_s=window_s)
            if not ok:
                log_security_event("rate_limited", {"ip": ip, "path": path, "limit": limit, "window_s": window_s})
                return JSONResponse({"detail": "Too many requests. Please slow down."}, status_code=429)
            break

    return await call_next(request)


# -------------------------
# PERFORMANCE METRICS
# -------------------------
@app.middleware("http")
async def perf_metrics_middleware(request: Request, call_next):
    started = time.perf_counter()
    try:
        return await call_next(request)
    finally:
        try:
            dt = max(0.0, time.perf_counter() - started)
            performance_metrics.observe_api(request.url.path or "/", dt)
        except Exception:
            pass


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
async def gmail_webhook(request: Request, user_id: str = None):
    """
    Gmail Pub/Sub webhook handler.

    Routes incoming Gmail notifications to the correct user based on:
    1. Explicit user_id query parameter (for debugging/fallback)
    2. Email lookup in users.json (requires email to be stored during setup)

    IMPORTANT: Gmail historyId changes with every message and CANNOT be used
    for routing. The old code tried to match incoming historyId with stored
    historyId - this never worked because historyId is transient per event.

    For production: Configure Cloud Pub/Sub message attributes to include
    the user email address, then extract it from message attributes.
    """

    body = await request.json()

    message = body.get("message", {})
    data = message.get("data")

    # Try to extract user from message attributes (Cloud Pub/Sub feature)
    message_attributes = message.get("attributes", {})
    attr_user_id = message_attributes.get("user_id") or message_attributes.get("email")

    if not data:
        return {"status": "no data"}

    decoded = base64.b64decode(data).decode("utf-8")
    payload = json.loads(decoded)

    history_id = payload.get("historyId")

    print("Gmail event received - historyId:", history_id)

    # -------------------------
    # FIND USER FROM MAPPING
    # -------------------------
    users_file = USERS_FILE

    if not users_file.exists():
        return {"status": "no user mapping"}

    with open(users_file, "r", encoding="utf-8") as f:
        users = json.load(f)

    # Priority order for user identification:
    # 1. Explicit query parameter (testing/fallback)
    # 2. Message attribute (Cloud Pub/Sub configured with user info)
    # 3. Email lookup (if only one user or email encoded in subscription)

    identified_user_id = None

    if user_id and user_id in users:
        identified_user_id = user_id
        print(f"✅ Routed via query parameter: {user_id}")
    elif attr_user_id:
        # Try message attribute user_id or email
        identified_user_id = attr_user_id if attr_user_id in users else None
        if not identified_user_id:
            # Try to find by email if attribute is an email
            for uid, info in users.items():
                if info.get("email", "").lower() == attr_user_id.lower():
                    identified_user_id = uid
                    break
        if identified_user_id:
            print(f"✅ Routed via message attributes: {identified_user_id}")
    else:
        # Fallback: use the most recently added user (single-user common case)
        if users:
            identified_user_id = next(iter(users.keys()))
            print(f"⚠️  No explicit routing info - using most recent user: {identified_user_id}")

    if not identified_user_id:
        print("❌ Could not identify user for Gmail webhook")
        print("   Solution 1: Pass ?user_id=X query parameter")
        print("   Solution 2: Configure Cloud Pub/Sub message attributes with user_id or email")
        print("   Solution 3: Ensure at least one Gmail account is connected")
        return {"status": "user not found - check routing configuration"}

    user_id = identified_user_id

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
app.include_router(user_router, prefix="/api/user", tags=["User"])
app.include_router(voice_router, prefix="/api")
app.include_router(voice_input_router, prefix="/api", tags=["Voice"])
app.include_router(voice_input_router, tags=["Voice"])
app.include_router(rag_router, prefix="/api/rag", tags=["RAG"])
app.include_router(gsuite_router, prefix="/api/gsuite", tags=["Google"])
app.include_router(events_router, prefix="/api/events", tags=["Events"])
app.include_router(memory_router, prefix="/memory", tags=["Memory"])
app.include_router(documents_router, prefix="/documents", tags=["Documents"])
app.include_router(documents_router, prefix="/api/documents", tags=["Documents"])
app.include_router(learning_router, prefix="/api/learning", tags=["Learning"])
app.include_router(system_router, tags=["System"])
app.include_router(system_router, prefix="/api", tags=["System"])


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
