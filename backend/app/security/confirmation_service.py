from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from app.security.security_logs import log_security_event


@dataclass(frozen=True)
class PendingConfirmation:
    user_id: str
    task: Dict[str, Any]
    prompt: str
    created_at: float
    expires_at: float


class ConfirmationService:
    """
    Simple in-memory confirmation store.

    Sensitive and critical commands are stored until the user explicitly confirms
    ("yes", "confirm", "go ahead") or cancels.
    """

    def __init__(self):
        self._pending: Dict[str, PendingConfirmation] = {}

    def set_pending(self, user_id: str, task: Dict[str, Any], *, prompt: str, ttl_s: float = 90.0) -> PendingConfirmation:
        uid = (user_id or "").strip() or "default"
        now = time.time()
        pending = PendingConfirmation(
            user_id=uid,
            task=dict(task or {}),
            prompt=prompt,
            created_at=now,
            expires_at=now + max(10.0, float(ttl_s)),
        )
        self._pending[uid] = pending
        log_security_event("confirmation.pending", {"user_id": uid, "action": pending.task.get("action"), "task": pending.task.get("text", "")})
        return pending

    def get_pending(self, user_id: str) -> Optional[PendingConfirmation]:
        uid = (user_id or "").strip() or "default"
        p = self._pending.get(uid)
        if not p:
            return None
        if time.time() > p.expires_at:
            self._pending.pop(uid, None)
            return None
        return p

    def clear_pending(self, user_id: str) -> None:
        uid = (user_id or "").strip() or "default"
        if uid in self._pending:
            self._pending.pop(uid, None)
            log_security_event("confirmation.cleared", {"user_id": uid})

    def classify_reply(self, user_text: str) -> str:
        """
        Returns: "confirm" | "cancel" | "other"
        """
        t = (user_text or "").strip().lower()
        if t in {"yes", "y", "confirm", "confirmed", "ok", "okay", "go ahead", "do it", "proceed"}:
            return "confirm"
        if t in {"no", "n", "cancel", "stop", "never mind", "dont", "don't"}:
            return "cancel"
        return "other"


confirmation_service = ConfirmationService()

