import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config.paths import TOKENS_DIR, CREDENTIALS_FILE
from app.services.google_token_store import load_gmail_credentials, save_gmail_credentials
from app.core.auth import create_token
from app.database.db import SessionLocal
from app.database.models import User

router = APIRouter()

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
    return save_gmail_credentials(user_id, creds)


@router.get("/gmail/login")
async def gmail_login(user_id: str = "default"):
    import asyncio
    import json
    import logging
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    logger = logging.getLogger(__name__)
    creds_path = CREDENTIALS_FILE

    if not Path(creds_path).exists():
        raise HTTPException(
            status_code=400,
            detail="Google credentials file not found. Please upload credentials.json first.",
        )

    def do_oauth():
        try:
            logger.info("Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), SCOPES
            )
            creds = flow.run_local_server(
                port=0,
                prompt="consent",
                authorization_prompt_message="",
                success_message="Gmail connected! You can close this tab and return to Jarvis.",
                open_browser=True,
            )
            logger.info("OAuth flow completed, getting profile...")

            profile_api = build("oauth2", "v2", credentials=creds)
            profile = profile_api.userinfo().get().execute()
            email = profile.get("email", "")
            name = profile.get("name", "User")

            logger.info(f"Got profile: {email}")

            # FIX: save to TOKENS_DIR — same path gmail_agent.py reads from
            _ensure_token_file(user_id, creds)
            logger.info("Token saved (encrypted) for user_id=%s", user_id)
            return {"email": email, "name": name}
        except Exception as e:
            logger.error(f"OAuth error: {e}")
            raise

    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = await loop.run_in_executor(pool, do_oauth)

        return {
            "status": "gmail connected",
            "user_id": user_id,
            "email": result["email"],
            "name": result["name"],
        }
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Gmail OAuth failed: {str(exc)[:300]}"
        )


@router.get("/connect-gmail")
async def connect_gmail(user_id: str = "default"):
    return await gmail_login(user_id=user_id)


@router.get("/gmail/profile")
def gmail_profile(user_id: str = "default"):
    try:
        creds = load_gmail_credentials(user_id, scopes=SCOPES)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Gmail token not found")
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            _ensure_token_file(user_id, creds)
        else:
            raise HTTPException(status_code=401, detail="Token invalid or expired")

    profile_api = build("oauth2", "v2", credentials=creds)
    profile = profile_api.userinfo().get().execute()
    email = profile.get("email")
    name = profile.get("name")

    user = _upsert_google_user(email=email, name=name)

    # FIX: always use user.user_id (string UUID), never user.id (integer)
    internal_user_id = user.user_id if user else user_id
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
    try:
        creds = load_gmail_credentials(user_id, scopes=SCOPES)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Gmail token not found")
    if not creds.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")

    creds.refresh(GoogleRequest())
    _ensure_token_file(user_id, creds)

    return {"status": "ok", "message": "Token refreshed"}
