from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.paths import LOG_DIR


_LOGGER_NAME = "email_automation"
_configured = False


def get_email_logger() -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = Path(LOG_DIR) / "email.log"

    handler = logging.FileHandler(str(log_path), encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    _configured = True
    return logger


def log_email_event(event: str, data: Dict[str, Any], *, error: Optional[str] = None) -> None:
    payload = {"event": event, "data": data, "error": error}
    try:
        get_email_logger().info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        # Best-effort: do not fail app logic due to logging.
        return

