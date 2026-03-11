from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from app.monitoring.monitor_logs import log_monitor_event
from app.monitoring.status_registry import Alert, status_registry
from app.services.event_bus import get_event_bus


class AlertManager:
    """
    Alert emitter with simple dedupe/throttle.
    """

    def __init__(self) -> None:
        self._last_sent: Dict[Tuple[str, str, str], float] = {}

    async def emit(
        self,
        *,
        level: str,
        component: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        min_interval_s: float = 120.0,
    ) -> None:
        lvl = (level or "info").strip().lower()
        comp = (component or "system").strip().lower()
        msg = (message or "").strip() or "Alert"
        key = (lvl, comp, msg)

        now = time.time()
        last = self._last_sent.get(key)
        if last is not None and (now - last) < float(min_interval_s):
            return
        self._last_sent[key] = now

        payload = {"level": lvl, "component": comp, "message": msg, "data": data or {}, "ts": now}
        try:
            status_registry.add_alert(Alert(ts=now, level=lvl, component=comp, message=msg, data=data or {}))
        except Exception:
            pass
        try:
            log_monitor_event("alert", payload)
        except Exception:
            pass
        try:
            await get_event_bus().publish("alert.new", payload)
        except Exception:
            return


alert_manager = AlertManager()

