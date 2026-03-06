import json
import os
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.agents.gmail_agent import GmailAgent
from app.config.paths import DATA_DIR, TOKENS_DIR, CREDENTIALS_FILE, USERS_FILE
from app.core.auth import create_token
from app.database.db import SessionLocal
from app.database.models import User

router = APIRouter()

# In-memory cache for OAuth state (maps state -> user_id, flow, timestamp)
_oauth_state_cache = {}

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
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    token_path = TOKENS_DIR / f"{user_id}_gmail_token.json"
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return str(token_path)


@router.get("/gmail/login")
def gmail_login(user_id: str = "default", request: Request = None):
    # Detect if running in Electron
    user_agent = (request.headers.get("user-agent") or "").lower() if request else ""

    if "electron" in user_agent:
        # Electron app - use new OAuth flow via /init
        return gmail_login_init(user_id)

    # Web/standalone - use old flow with local server
    if not CREDENTIALS_FILE.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                "Google OAuth credentials are missing. "
                "Upload credentials.json in Settings before connecting Gmail."
            ),
        )

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Google OAuth failed to start: {exc}",
        )

    profile_api = build("oauth2", "v2", credentials=creds)
    profile = profile_api.userinfo().get().execute()
    email = profile.get("email")
    name = profile.get("name")

    user = _upsert_google_user(email=email, name=name)

    # FIX: always use user.user_id (string UUID), never user.id (integer)
    internal_user_id = user.user_id if user else user_id

    _ensure_token_file(user_id, creds)
    _ensure_token_file(internal_user_id, creds)

    history_id = None
    watch_enabled = False

    if PUBSUB_TOPIC and "YOUR_PROJECT_ID" not in PUBSUB_TOPIC:
        gmail_agent = GmailAgent(user_id=internal_user_id)
        watch_response = gmail_agent.start_watch(PUBSUB_TOPIC)
        history_id = watch_response.get("historyId")
        watch_enabled = True

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if USERS_FILE.exists():
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)
        else:
            users = {}

        users[internal_user_id] = {
            "email": email,
            "historyId": history_id,
        }

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


@router.get("/gmail/login/init")
def gmail_login_init(user_id: str = "default"):
    """Initialize OAuth flow for Electron app - returns authorization URL"""
    if not CREDENTIALS_FILE.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                "Google OAuth credentials are missing. "
                "Upload credentials.json in Settings before connecting Gmail."
            ),
        )

    try:
        # Load and validate credentials file
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            creds_data = json.load(f)

        # Check for redirect_uri in credentials
        redirect_uris = (
            creds_data.get("installed", {}).get("redirect_uris", [])
            or creds_data.get("web", {}).get("redirect_uris", [])
            or []
        )

        expected_redirect = "http://localhost:8000/api/auth/gmail/callback"
        if expected_redirect not in redirect_uris:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Redirect URI not configured. "
                    f"Add '{expected_redirect}' to Google OAuth credentials redirect_uris "
                    "in Google Cloud Console and re-upload credentials.json in Settings."
                ),
            )

        # Create flow and generate authorization URL
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
        )

        # Store state mapping for callback (10 minute expiry)
        _oauth_state_cache[state] = {
            "user_id": user_id,
            "flow": flow,
            "timestamp": datetime.utcnow(),
        }

        return {
            "auth_url": auth_url,
            "state": state,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to initialize OAuth flow: {str(exc)[:100]}",
        )


@router.get("/gmail/callback")
def gmail_callback(code: str = None, state: str = None, request: Request = None):
    """OAuth callback endpoint - receives code from Google and completes token exchange"""
    try:
        # Validate parameters
        if not code or not state:
            return HTMLResponse(
                content="<html><body><p style='color:red;'>OAuth Error: Missing code or state</p></body></html>",
                status_code=400,
            )

        # Retrieve and validate state
        if state not in _oauth_state_cache:
            return HTMLResponse(
                content=(
                    "<html><body><p style='color:red;'>OAuth Error: Invalid or expired state</p>"
                    "<script>setTimeout(() => window.close(), 3000)</script></body></html>"
                ),
                status_code=400,
            )

        cached = _oauth_state_cache[state]

        # Check if state expired (older than 10 minutes)
        if datetime.utcnow() - cached["timestamp"] > timedelta(minutes=10):
            del _oauth_state_cache[state]
            return HTMLResponse(
                content=(
                    "<html><body><p style='color:red;'>OAuth Error: State expired, please try again</p>"
                    "<script>setTimeout(() => window.close(), 3000)</script></body></html>"
                ),
                status_code=400,
            )

        user_id = cached["user_id"]
        flow = cached["flow"]

        # Exchange authorization code for tokens
        if request:
            authorization_response = str(request.url)
        else:
            authorization_response = f"http://localhost:8000/api/auth/gmail/callback?code={code}&state={state}"

        creds = flow.fetch_token(authorization_response=authorization_response)

        # Get user profile
        profile_api = build("oauth2", "v2", credentials=creds)
        profile = profile_api.userinfo().get().execute()
        email = profile.get("email")
        name = profile.get("name")

        # Store tokens
        _ensure_token_file(user_id, creds)

        # Upsert Google user
        user = _upsert_google_user(email=email, name=name)

        # FIX: always use user.user_id (string UUID), never user.id (integer)
        internal_user_id = user.user_id if user else user_id
        _ensure_token_file(internal_user_id, creds)

        # Clean up state
        del _oauth_state_cache[state]

        return HTMLResponse(
            content=f"""
            <html>
            <head><title>Gmail Connected</title></head>
            <body style='text-align: center; padding: 20px; font-family: Arial, sans-serif;'>
                <p style='color: green; font-size: 18px; margin-bottom: 10px;'>✓ Gmail connected successfully</p>
                <p style='color: #333; font-size: 14px; margin-bottom: 5px;'>{email}</p>
                <p style='color: #666; font-size: 12px;'>Closing in 3 seconds...</p>
                <script>
                    setTimeout(() => window.close(), 3000);
                </script>
            </body>
            </html>
            """
        )

    except Exception as exc:
        error_msg = str(exc)[:100]
        return HTMLResponse(
            content=f"""
            <html>
            <body style='text-align: center; padding: 20px; font-family: Arial, sans-serif;'>
                <p style='color: red; font-size: 16px; margin-bottom: 10px;'>✗ OAuth Error</p>
                <p style='color: #333; font-size: 12px;'>{error_msg}</p>
                <p style='color: #666; font-size: 11px; margin-top: 15px;'>Closing in 5 seconds...</p>
                <script>
                    setTimeout(() => window.close(), 5000);
                </script>
            </body>
            </html>
            """,
            status_code=400,
        )


@router.get("/connect-gmail")
def connect_gmail(user_id: str = "default"):
    return gmail_login(user_id=user_id)


@router.get("/gmail/profile")
def gmail_profile(user_id: str = "default"):
    token_path = TOKENS_DIR / f"{user_id}_gmail_token.json"
    if not token_path.exists():
        raise HTTPException(status_code=404, detail="Gmail token not found")

    creds = Credentials.from_authorized_user_file(str(token_path))
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            with open(token_path, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
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
    token_path = TOKENS_DIR / f"{user_id}_gmail_token.json"
    if not token_path.exists():
        raise HTTPException(status_code=404, detail="Gmail token not found")

    creds = Credentials.from_authorized_user_file(str(token_path))
    if not creds.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")

    creds.refresh(GoogleRequest())
    with open(token_path, "w", encoding="utf-8") as token_file:
        token_file.write(creds.to_json())

    return {"status": "ok", "message": "Token refreshed"}
