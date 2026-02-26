import json
import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.agents.gmail_agent import GmailAgent
from app.core.auth import create_token
from app.database.db import SessionLocal
from app.models.user import User

router = APIRouter()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
TOKENS_DIR = os.path.join(DATA_DIR, "tokens")
CREDENTIALS_FILE = os.path.join(DATA_DIR, "credentials", "credentials.json")
USERS_FILE = os.path.join(DATA_DIR, "pubsub_users.json")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
if os.getenv("ENABLE_CALENDAR_SCOPE", "false").lower() == "true":
    SCOPES.append("https://www.googleapis.com/auth/calendar.readonly")

PUBSUB_TOPIC = os.getenv("GMAIL_PUBSUB_TOPIC", "").strip()


def _upsert_google_user(email: str | None, name: str | None) -> User | None:
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == normalized_email).first()
        if not user:
            user = User(
                email=normalized_email,
                name=(name or "").strip(),
                user_id=f"user:{uuid4().hex}",
                password=None,
            )
            db.add(user)
        else:
            if name and not user.name:
                user.name = (name or "").strip()
            if not user.user_id:
                user.user_id = f"user:{uuid4().hex}"
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _ensure_token_file(user_id: str, creds: Credentials) -> str:
    os.makedirs(TOKENS_DIR, exist_ok=True)
    token_path = os.path.join(TOKENS_DIR, f"{user_id}_gmail_token.json")
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return token_path


@router.get("/gmail/login")
def gmail_login(user_id: str = "default"):
    if not os.path.exists(CREDENTIALS_FILE):
        raise HTTPException(
            status_code=400,
            detail="Missing credentials file at app/data/credentials/credentials.json",
        )

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    profile_api = build("oauth2", "v2", credentials=creds)
    profile = profile_api.userinfo().get().execute()
    email = profile.get("email")
    name = profile.get("name")

    user = _upsert_google_user(email=email, name=name)
    internal_user_id = str(user.id) if user else user_id

    _ensure_token_file(user_id, creds)
    _ensure_token_file(internal_user_id, creds)

    history_id = None
    watch_enabled = False

    if PUBSUB_TOPIC and "YOUR_PROJECT_ID" not in PUBSUB_TOPIC:
        gmail_agent = GmailAgent(user_id=internal_user_id)
        watch_response = gmail_agent.start_watch(PUBSUB_TOPIC)
        history_id = watch_response.get("historyId")
        watch_enabled = True

        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)
        else:
            users = {}

        users[internal_user_id] = {"historyId": history_id}

        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)

    return {
        "status": "gmail connected",
        "user": internal_user_id,
        "user_id": internal_user_id,
        "email": email,
        "name": name,
        "token": create_token(internal_user_id, email=email) if user else None,
        "historyId": history_id,
        "watch_enabled": watch_enabled,
    }


@router.get("/connect-gmail")
def connect_gmail(user_id: str = "default"):
    return gmail_login(user_id=user_id)


@router.get("/gmail/profile")
def gmail_profile(user_id: str = "default"):
    token_path = os.path.join(TOKENS_DIR, f"{user_id}_gmail_token.json")
    if not os.path.exists(token_path):
        raise HTTPException(status_code=404, detail="Gmail token not found")

    creds = Credentials.from_authorized_user_file(token_path)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
        else:
            raise HTTPException(status_code=401, detail="Token invalid or expired")

    profile_api = build("oauth2", "v2", credentials=creds)
    profile = profile_api.userinfo().get().execute()
    email = profile.get("email")
    name = profile.get("name")

    user = _upsert_google_user(email=email, name=name)
    internal_user_id = str(user.id) if user else user_id
    _ensure_token_file(internal_user_id, creds)

    return {
        "status": "ok",
        "email": email,
        "name": name,
        "user_id": internal_user_id,
        "token": create_token(internal_user_id, email=email) if user else None,
    }


@router.post("/gmail/refresh")
def gmail_refresh_token(user_id: str = "default"):
    token_path = os.path.join(TOKENS_DIR, f"{user_id}_gmail_token.json")
    if not os.path.exists(token_path):
        raise HTTPException(status_code=404, detail="Gmail token not found")

    creds = Credentials.from_authorized_user_file(token_path)
    if not creds.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")

    creds.refresh(Request())
    with open(token_path, "w", encoding="utf-8") as token_file:
        token_file.write(creds.to_json())

    return {"status": "ok", "message": "Token refreshed"}
