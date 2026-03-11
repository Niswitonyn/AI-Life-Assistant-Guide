from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    api_host: str
    api_port: int
    data_directory: Path
    log_directory: Path
    download_directory: Path


def load_config() -> AppConfig:
    api_host = os.getenv("API_HOST", "127.0.0.1")
    api_port = int(os.getenv("API_PORT", "8000"))

    data_dir = Path(os.getenv("AI_LIFE_DATA_DIR", str(Path.cwd() / "data"))).expanduser().resolve()
    log_dir = Path(os.getenv("AI_LIFE_LOG_DIR", str(data_dir / "logs"))).expanduser().resolve()
    dl_dir = Path(os.getenv("AI_LIFE_DOWNLOAD_DIR", str(Path.home() / "Downloads"))).expanduser().resolve()

    return AppConfig(
        api_host=api_host,
        api_port=api_port,
        data_directory=data_dir,
        log_directory=log_dir,
        download_directory=dl_dir,
    )

