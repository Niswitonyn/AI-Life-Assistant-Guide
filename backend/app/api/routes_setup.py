import os
import json
from fastapi import APIRouter, UploadFile, File, Body
from app.config.paths import (
    DATA_DIR,
    CREDENTIALS_DIR,
    CREDENTIALS_FILE,
    TOKENS_DIR,
    AI_CONFIG_PATH,
    USER_CONFIG_PATH,
)

router = APIRouter()

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

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    with open(CREDENTIALS_FILE, "wb") as f:
        f.write(await file.read())

    return {"status": "gmail credentials saved"}


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
