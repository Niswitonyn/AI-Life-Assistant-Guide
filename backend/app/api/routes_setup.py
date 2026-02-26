import os
import json
from fastapi import APIRouter, UploadFile, File, Body

router = APIRouter()

# -------------------------
# PATHS
# -------------------------
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

DATA_DIR = os.path.join(BASE_DIR, "data")

CREDENTIALS_DIR = os.path.join(DATA_DIR, "credentials")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials.json")

TOKENS_DIR = os.path.join(DATA_DIR, "tokens")

AI_CONFIG_PATH = os.path.join(DATA_DIR, "ai_config.json")
USER_CONFIG_PATH = os.path.join(DATA_DIR, "user.json")


# -------------------------
# STATUS CHECK
# -------------------------
@router.get("/status")
def setup_status():

    ai_ready = os.path.exists(AI_CONFIG_PATH)
    gmail_ready = (
        os.path.exists(CREDENTIALS_FILE) or
        (
            os.path.exists(TOKENS_DIR) and
            any(name.endswith("_gmail_token.json") for name in os.listdir(TOKENS_DIR))
        )
    )
    user_ready = os.path.exists(USER_CONFIG_PATH)

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

    os.makedirs(DATA_DIR, exist_ok=True)

    with open(USER_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)

    return {"status": "user saved"}


# -------------------------
# GMAIL SETUP
# -------------------------
@router.post("/gmail")
async def setup_gmail(file: UploadFile = File(...)):

    os.makedirs(CREDENTIALS_DIR, exist_ok=True)

    with open(CREDENTIALS_FILE, "wb") as f:
        f.write(await file.read())

    return {"status": "gmail credentials saved"}


# -------------------------
# AI SETUP
# -------------------------
@router.post("/ai")
async def setup_ai(data: dict = Body(...)):

    os.makedirs(DATA_DIR, exist_ok=True)

    with open(AI_CONFIG_PATH, "w") as f:
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

    if os.path.exists(TOKENS_DIR):
        for f in os.listdir(TOKENS_DIR):
            os.remove(os.path.join(TOKENS_DIR, f))

    if os.path.exists(CREDENTIALS_FILE):
        os.remove(CREDENTIALS_FILE)

    return {"status": "gmail disconnected"}


# -------------------------
# RECONNECT AI
# -------------------------
@router.post("/reconnect-ai")
def reconnect_ai():

    if os.path.exists(AI_CONFIG_PATH):
        os.remove(AI_CONFIG_PATH)

    return {"status": "ai reset"}
