from pydantic import field_validator
from pydantic_settings import BaseSettings
from app.config.paths import DATA_DIR, DB_DIR, LOG_DIR, KEYS_DIR_PATH


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
    JWT_SECRET_KEY: str = "change-this-jwt-secret"
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
