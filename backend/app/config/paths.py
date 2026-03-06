import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def resolve_data_dir() -> Path:
    override = os.getenv("AI_LIFE_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return BASE_DIR / "data"


DATA_DIR = resolve_data_dir()
DB_DIR = DATA_DIR / "database"
LOG_DIR = DATA_DIR / "logs"
KEYS_DIR_PATH = DATA_DIR / "keys"
TOKENS_DIR = DATA_DIR / "tokens"
CREDENTIALS_DIR = DATA_DIR / "credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"
USERS_FILE = DATA_DIR / "pubsub_users.json"
AI_CONFIG_PATH = DATA_DIR / "ai_config.json"
USER_CONFIG_PATH = DATA_DIR / "user.json"
CONTACTS_FILE = DATA_DIR / "contacts.json"
RAG_STORE_FILE = DATA_DIR / "rag_store.json"

