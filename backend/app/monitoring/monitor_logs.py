from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.paths import BASE_DIR, LOG_DIR


_LOGGER_NAME = "system_monitor"
_configured = False


def get_monitor_logger() -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = Path(LOG_DIR) / "system_monitor.log"

    handler = logging.FileHandler(str(log_path), encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))

    legacy_dir = Path(BASE_DIR) / "logs"
    legacy_handler = None
    try:
        legacy_dir.mkdir(parents=True, exist_ok=True)
        legacy_path = legacy_dir / "system_monitor.log"
        legacy_handler = logging.FileHandler(str(legacy_path), encoding="utf-8")
        legacy_handler.setLevel(logging.INFO)
        legacy_handler.setFormatter(logging.Formatter("%(message)s"))
    except Exception:
        legacy_handler = None

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    if legacy_handler:
        logger.addHandler(legacy_handler)
    logger.propagate = False

    _configured = True
    return logger


def log_monitor_event(event: str, data: Dict[str, Any], *, error: Optional[str] = None) -> None:
    payload = {"ts": time.time(), "event": event, "data": data, "error": error}
    try:
        get_monitor_logger().info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        return

