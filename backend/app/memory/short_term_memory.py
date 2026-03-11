from collections import defaultdict, deque
from typing import Deque, Dict, List


class ShortTermMemory:
    """
    In-process short-lived memory window per user.
    """

    def __init__(self, max_items: int = 20):
        self.max_items = max_items
        self._buffers: Dict[str, Deque[dict]] = defaultdict(lambda: deque(maxlen=self.max_items))

    def push(self, user_id: str, role: str, content: str) -> None:
        uid = (user_id or "").strip() or "default"
        self._buffers[uid].append({"role": role, "content": content})

    def get_recent(self, user_id: str, limit: int = 10) -> List[dict]:
        uid = (user_id or "").strip() or "default"
        items = list(self._buffers.get(uid, []))
        return items[-max(1, limit):]

    def clear(self, user_id: str) -> None:
        uid = (user_id or "").strip() or "default"
        self._buffers.pop(uid, None)
