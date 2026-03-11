from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Generic, Optional, Tuple, TypeVar


K = TypeVar("K")
V = TypeVar("V")


def _now() -> float:
    return time.time()


@dataclass
class _Item(Generic[V]):
    value: V
    expires_at: float


class TTLCache(Generic[K, V]):
    """
    Tiny in-memory TTL cache (thread-safe).

    - Best-effort eviction; designed for small caches.
    - Not intended for sensitive data.
    """

    def __init__(self, *, ttl_s: float = 30.0, max_items: int = 256):
        self.ttl_s = float(ttl_s)
        self.max_items = max(8, int(max_items))
        self._lock = threading.Lock()
        self._data: Dict[K, _Item[V]] = {}

    def get(self, key: K) -> Optional[V]:
        now = _now()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            if item.expires_at <= now:
                self._data.pop(key, None)
                return None
            return item.value

    def set(self, key: K, value: V, *, ttl_s: Optional[float] = None) -> None:
        ttl = self.ttl_s if ttl_s is None else float(ttl_s)
        exp = _now() + max(0.1, ttl)
        with self._lock:
            if len(self._data) >= self.max_items:
                self._evict_locked()
            self._data[key] = _Item(value=value, expires_at=exp)

    def get_or_set(self, key: K, factory: Callable[[], V], *, ttl_s: Optional[float] = None) -> V:
        existing = self.get(key)
        if existing is not None:
            return existing
        value = factory()
        self.set(key, value, ttl_s=ttl_s)
        return value

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def _evict_locked(self) -> None:
        now = _now()
        # Remove expired first.
        expired = [k for k, it in self._data.items() if it.expires_at <= now]
        for k in expired[: max(1, len(expired))]:
            self._data.pop(k, None)
        if len(self._data) < self.max_items:
            return
        # Remove a few arbitrary items (small cache).
        for k in list(self._data.keys())[: max(1, self.max_items // 8)]:
            self._data.pop(k, None)

