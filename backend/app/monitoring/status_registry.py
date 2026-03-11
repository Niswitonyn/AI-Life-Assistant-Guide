from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Alert:
    ts: float
    level: str  # info|warning|critical
    component: str
    message: str
    data: Dict[str, Any]


class StatusRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._health: Dict[str, Any] = {
            "status": "unknown",
            "checked_at": None,
            "components": {},
            "metrics": {},
        }
        self._alerts: List[Alert] = []

    def set_snapshot(self, snapshot: Dict[str, Any]) -> None:
        with self._lock:
            self._health = dict(snapshot or {})

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._health)

    def add_alert(self, alert: Alert, *, max_items: int = 50) -> None:
        with self._lock:
            self._alerts.insert(0, alert)
            self._alerts = self._alerts[: max(1, int(max_items))]

    def get_alerts(self, *, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            out = []
            for a in self._alerts[: max(1, int(limit))]:
                out.append(
                    {
                        "ts": a.ts,
                        "level": a.level,
                        "component": a.component,
                        "message": a.message,
                        "data": a.data,
                    }
                )
            return out


status_registry = StatusRegistry()

