import os
from pathlib import Path

import uvicorn
from app.main import app as fastapi_app


def _default_data_dir() -> str:
    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        return str(Path(appdata) / "Jarvis Assistant" / "backend-data")
    return str(Path.cwd() / "data")


if "AI_LIFE_DATA_DIR" not in os.environ:
    os.environ["AI_LIFE_DATA_DIR"] = _default_data_dir()


def main():
    uvicorn.run(
        fastapi_app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
