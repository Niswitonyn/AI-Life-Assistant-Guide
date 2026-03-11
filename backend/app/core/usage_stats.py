from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.paths import DATA_DIR


@dataclass(frozen=True)
class UsageEvent:
    kind: str
    value: str


class UsageStatsStore:
    """
    Tiny file-backed usage stats store (best-effort).
    """

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (DATA_DIR / "usage_stats.json")
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, int]] = {"app_open": {}, "web_query": {}, "file_location": {}}
        self._load()

    def _load(self) -> None:
        try:
            if not self.path.exists():
                self._flush()
                return
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self._data, dict):
                self._data = {"app_open": {}, "web_query": {}, "file_location": {}}
        except Exception:
            self._data = {"app_open": {}, "web_query": {}, "file_location": {}}

    def _flush(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            return

    def bump(self, kind: str, value: str) -> None:
        k = (kind or "").strip()
        v = (value or "").strip()
        if not k or not v:
            return
        with self._lock:
            bucket = self._data.setdefault(k, {})
            bucket[v] = int(bucket.get(v, 0)) + 1
            self._flush()


usage_stats = UsageStatsStore()

