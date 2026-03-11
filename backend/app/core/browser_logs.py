from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional


logger = logging.getLogger("browser_automation")


@dataclass
class _BrowserLogState:
    command: str
    task: str
    start: float
    download_count: int = 0
    error: Optional[str] = None


class _BrowserLogHandle:
    def __init__(self, state: _BrowserLogState):
        self._state = state

    def add_download_count(self, count: int) -> None:
        try:
            self._state.download_count += max(0, int(count))
        except Exception:
            return


@asynccontextmanager
async def browser_log(command: str, task: str = "") -> AsyncIterator[_BrowserLogHandle]:
    state = _BrowserLogState(command=command, task=task, start=time.perf_counter())
    handle = _BrowserLogHandle(state)
    _emit("start", state)
    try:
        yield handle
        _emit("end", state)
    except Exception as e:
        state.error = str(e) or "error"
        _emit("error", state)
        raise


def _emit(event: str, state: _BrowserLogState) -> None:
    elapsed_ms = int((time.perf_counter() - state.start) * 1000)
    payload: Dict[str, Any] = {
        "event": event,
        "command": state.command,
        "task": state.task,
        "elapsed_ms": elapsed_ms,
        "download_count": state.download_count,
        "error": state.error,
    }
    try:
        logger.info(json.dumps(payload, ensure_ascii=False))
    except Exception:
        logger.info("%s %s %sms", state.command, event, elapsed_ms)

