from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Tuple


@dataclass(frozen=True)
class RateLimit:
    limit: int
    window_s: float


class RateLimiter:
    def __init__(self):
        self._hits: Dict[Tuple[str, str], Deque[float]] = {}

    def allow(self, key: str, bucket: str, *, limit: int, window_s: float) -> bool:
        now = time.time()
        k = (key, bucket)
        q = self._hits.get(k)
        if q is None:
            q = deque()
            self._hits[k] = q
        while q and (now - q[0] > window_s):
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


rate_limiter = RateLimiter()

