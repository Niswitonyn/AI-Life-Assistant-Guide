import os
import json
from fastapi import APIRouter, UploadFile, File, Body, HTTPException
from app.config.paths import (
    DATA_DIR,
    CREDENTIALS_DIR,
    CREDENTIALS_FILE,
    TOKENS_DIR,
    AI_CONFIG_PATH,
    USER_CONFIG_PATH,
)

router = APIRouter()


def _validate_google_credentials(payload: dict) -> dict:
    client_block = payload.get("installed") or payload.get("web")
    if not isinstance(client_block, dict):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid Google OAuth JSON. Expected top-level 'installed' or 'web' object."
            ),
        )

    required = ["client_id", "client_secret", "auth_uri", "token_uri"]
    missing = [key for key in required if not str(client_block.get(key, "")).strip()]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid Google OAuth JSON. Missing keys: {', '.join(missing)}",
        )

    return {
        "client_id": client_block.get("client_id", ""),
        "project_id": client_block.get("project_id", ""),
        "type": "installed" if "installed" in payload else "web",
    }

# -------------------------
# STATUS CHECK
# -------------------------
@router.get("/status")
def setup_status():

    ai_ready = AI_CONFIG_PATH.exists()
    gmail_ready = (
        CREDENTIALS_FILE.exists() or
        (
            TOKENS_DIR.exists() and
            any(name.endswith("_gmail_token.json") for name in os.listdir(TOKENS_DIR))
        )
    )
    user_ready = USER_CONFIG_PATH.exists()

    return {
        "configured": ai_ready and gmail_ready and user_ready,
        "ai_ready": ai_ready,
        "gmail_ready": gmail_ready,
        "user_ready": user_ready
    }


# -------------------------
# USER SETUP
# -------------------------
@router.post("/user")
async def setup_user(data: dict = Body(...)):

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return {"status": "user saved"}


# -------------------------
# GMAIL SETUP
# -------------------------
@router.post("/gmail")
async def setup_gmail(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="Missing Google credentials file")

    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="credentials.json must be valid UTF-8 JSON")

    details = _validate_google_credentials(payload)

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    with open(CREDENTIALS_FILE, "wb") as f:
        f.write(raw)

    return {
        "status": "gmail credentials saved",
        "oauth_type": details["type"],
        "project_id": details["project_id"],
    }


@router.get("/gmail/status")
def gmail_status():
    token_users = []
    if TOKENS_DIR.exists():
        token_users = [
            name.replace("_gmail_token.json", "")
            for name in os.listdir(TOKENS_DIR)
            if name.endswith("_gmail_token.json")
        ]

    if not CREDENTIALS_FILE.exists():
        return {
            "has_credentials": False,
            "token_users": token_users,
            "message": "Google OAuth credentials are not configured",
        }

    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        details = _validate_google_credentials(payload)
        return {
            "has_credentials": True,
            "oauth_type": details["type"],
            "project_id": details["project_id"],
            "token_users": token_users,
            "message": "Google OAuth credentials are configured",
        }
    except HTTPException as exc:
        return {
            "has_credentials": False,
            "token_users": token_users,
            "message": exc.detail,
        }


# -------------------------
# AI SETUP
# -------------------------
@router.post("/ai")
async def setup_ai(data: dict = Body(...)):

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(AI_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return {"status": "ai config saved"}


# =====================================================
# SETTINGS ACTIONS (FOR SETTINGS PANEL)
# =====================================================

# -------------------------
# DISCONNECT GMAIL
# -------------------------
@router.post("/disconnect-gmail")
def disconnect_gmail():

    if TOKENS_DIR.exists():
        for f in os.listdir(TOKENS_DIR):
            (TOKENS_DIR / f).unlink(missing_ok=True)

    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink(missing_ok=True)

    return {"status": "gmail disconnected"}


# -------------------------
# RECONNECT AI
# -------------------------
@router.post("/reconnect-ai")
def reconnect_ai():

    if AI_CONFIG_PATH.exists():
        AI_CONFIG_PATH.unlink(missing_ok=True)

    return {"status": "ai reset"}
