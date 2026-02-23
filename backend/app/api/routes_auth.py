import os
import json
from fastapi import APIRouter
from google_auth_oauthlib.flow import InstalledAppFlow

from app.agents.gmail_agent import GmailAgent   # ✅ IMPORTANT

router = APIRouter()

# -------------------------
# PATHS
# -------------------------
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

DATA_DIR = os.path.join(BASE_DIR, "data")
TOKENS_DIR = os.path.join(DATA_DIR, "tokens")
CREDENTIALS_FILE = os.path.join(DATA_DIR, "credentials", "credentials.json")

USERS_FILE = os.path.join(DATA_DIR, "pubsub_users.json")

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# 🔴 CHANGE THIS TO YOUR PUBSUB TOPIC
PUBSUB_TOPIC = "projects/YOUR_PROJECT_ID/topics/YOUR_TOPIC_NAME"


# -------------------------
# CONNECT GMAIL + AUTO WATCH
# -------------------------
@router.get("/connect-gmail")
def connect_gmail(user_id: str = "default"):

    os.makedirs(TOKENS_DIR, exist_ok=True)

    token_path = os.path.join(
        TOKENS_DIR,
        f"{user_id}_gmail_token.json"
    )

    # -------------------------
    # OAUTH FLOW
    # -------------------------
    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_FILE,
        SCOPES
    )

    creds = flow.run_local_server(port=0)

    with open(token_path, "w") as f:
        f.write(creds.to_json())

    # -------------------------
    # START GMAIL WATCH
    # -------------------------
    gmail_agent = GmailAgent(user_id=user_id)

    watch_response = gmail_agent.start_watch(PUBSUB_TOPIC)

    history_id = watch_response.get("historyId")

    # -------------------------
    # SAVE USER MAPPING
    # -------------------------
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    else:
        users = {}

    users[user_id] = {
        "historyId": history_id
    }

    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

    return {
        "status": "gmail connected",
        "user": user_id,
        "historyId": history_id
    }