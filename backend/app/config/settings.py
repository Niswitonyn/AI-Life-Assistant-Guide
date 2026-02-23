from pathlib import Path
from pydantic_settings import BaseSettings


# -------------------------
# BASE PATHS
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR / "database"
LOG_DIR = DATA_DIR / "logs"
KEYS_DIR_PATH = DATA_DIR / "keys"


# -------------------------
# SETTINGS CLASS
# -------------------------
class Settings(BaseSettings):

    APP_NAME: str = "AI Life Assistant"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # IMPORTANT: SQLite path must be string
    DATABASE_URL: str = f"sqlite:///{(DB_DIR / 'assistant.db').as_posix()}"

    DEFAULT_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    KEYS_DIR: str = str(KEYS_DIR_PATH)
    ENCRYPTION_KEY_PATH: str = str(KEYS_DIR_PATH / "secret.key")


# -------------------------
# CREATE FOLDERS AUTOMATICALLY
# -------------------------
for directory in [DATA_DIR, DB_DIR, LOG_DIR, KEYS_DIR_PATH]:
    directory.mkdir(parents=True, exist_ok=True)


# -------------------------
# SETTINGS INSTANCE
# -------------------------
settings = Settings()