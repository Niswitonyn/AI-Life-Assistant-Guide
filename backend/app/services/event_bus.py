from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class Event:
    type: str
    data: Dict[str, Any]


class EventBus:
    def __init__(self):
        self._subscribers: List[asyncio.Queue[Event]] = []
        self._lock = asyncio.Lock()

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        event = Event(type=event_type, data=data)
        async with self._lock:
            for q in list(self._subscribers):
                try:
                    q.put_nowait(event)
                except Exception:
                    continue

    async def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)


_bus = EventBus()


def get_event_bus() -> EventBus:
    return _bus

