import os
import secrets
from pydantic import field_validator
from pydantic_settings import BaseSettings
from app.config.paths import DATA_DIR, DB_DIR, LOG_DIR, KEYS_DIR_PATH


def _init_jwt_secret() -> str:
    """
    Initialize or retrieve the JWT secret key.

    On first run: Generates a cryptographically secure random key and persists it.
    On subsequent runs: Retrieves the stored key from disk.

    This ensures:
    - The secret is never hardcoded in source
    - The secret persists across app restarts
    - Each deployment gets a unique, non-public secret
    """
    jwt_secret_file = KEYS_DIR_PATH / "jwt_secret.key"

    # Try to load existing secret from disk
    if jwt_secret_file.exists():
        try:
            with open(jwt_secret_file, "r") as f:
                secret = f.read().strip()
                if secret:
                    return secret
        except Exception as e:
            print(f"Warning: Could not read JWT secret file: {e}")

    # Generate new secret on first run
    secret = secrets.token_urlsafe(32)

    # Persist to disk
    try:
        jwt_secret_file.parent.mkdir(parents=True, exist_ok=True)
        jwt_secret_file.touch(mode=0o600)  # Owner read/write only
        with open(jwt_secret_file, "w") as f:
            f.write(secret)
    except Exception as e:
        print(f"Warning: Could not persist JWT secret to disk: {e}")

    return secret


# -------------------------
# BASE PATHS
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
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "") or _init_jwt_secret()
    JWT_EXPIRE_MINUTES: int = 10080

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _coerce_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value


# -------------------------
# CREATE FOLDERS AUTOMATICALLY
# -------------------------
for directory in [DATA_DIR, DB_DIR, LOG_DIR, KEYS_DIR_PATH]:
    directory.mkdir(parents=True, exist_ok=True)


# -------------------------
# SETTINGS INSTANCE
# -------------------------
settings = Settings()
