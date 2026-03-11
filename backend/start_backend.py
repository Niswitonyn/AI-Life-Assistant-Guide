from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from app.config.paths import DATA_DIR
from app.database.init_db import init_db
from app.main import app as fastapi_app


def _default_data_dir() -> str:
    # Prefer a portable directory when the launcher provides one.
    override = os.getenv("AI_LIFE_DATA_DIR", "").strip()
    if override:
        return override

    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        return str(Path(appdata) / "Jarvis Assistant" / "data")
    return str(Path.cwd() / "data")


def main() -> None:
    # Ensure data dir is set before importing modules that rely on it.
    if "AI_LIFE_DATA_DIR" not in os.environ:
        os.environ["AI_LIFE_DATA_DIR"] = _default_data_dir()

    # First-run init: ensure DB + folders exist.
    try:
        init_db()
    except Exception:
        # If DB init fails, uvicorn will still start and expose /health,
        # allowing the GUI to show a meaningful error or logs.
        pass

    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))

    uvicorn.run(
        fastapi_app,
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()

