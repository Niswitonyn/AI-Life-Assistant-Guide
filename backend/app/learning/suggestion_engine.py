from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database.models import UserBehavior
from app.learning.learning_logs import log_learning_event
from app.services.event_bus import get_event_bus


class SuggestionEngine:
    """
    Generates lightweight suggestions from behavior patterns.
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"

    def get_suggestions(self, *, limit: int = 5) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(UserBehavior)
            .filter(UserBehavior.user_id == self.user_id)
            .order_by(UserBehavior.frequency.desc())
            .limit(50)
            .all()
        )

        out: List[Dict[str, Any]] = []
        for r in rows:
            if len(out) >= max(1, int(limit)):
                break
            action = (r.action or "").strip()
            freq = int(r.frequency or 0)
            if action.startswith("open_app:") and freq >= 5:
                app = action.split("open_app:", 1)[-1].strip()
                out.append({"type": "open_app", "text": f"Open {app}", "command": f"open {app}", "score": freq})
            if action.startswith("web_search:") and freq >= 5:
                q = action.split("web_search:", 1)[-1].strip()
                out.append({"type": "web_search", "text": f"Search: {q}", "command": f"search {q}", "score": freq})
        return out[: max(1, int(limit))]

    async def maybe_emit(self, updated_row: UserBehavior) -> None:
        """
        Emit a suggestion event at common milestones.
        """
        try:
            freq = int(updated_row.frequency or 0)
            if freq not in {5, 10, 25}:
                return
            action = (updated_row.action or "").strip()
            suggestion = None
            if action.startswith("open_app:"):
                app = action.split("open_app:", 1)[-1].strip()
                suggestion = {"type": "suggestion.open_app", "text": f"You often open {app}. Want me to open it now?", "command": f"open {app}"}
            elif action.startswith("web_search:"):
                q = action.split("web_search:", 1)[-1].strip()
                suggestion = {"type": "suggestion.web_search", "text": f"You often search '{q}'. Want a quick update?", "command": f"search {q}"}
            if not suggestion:
                return

            # Avoid repeated spam: store last_suggested_freq in context.
            try:
                ctx = json.loads(updated_row.context or "{}") if updated_row.context else {}
            except Exception:
                ctx = {}
            last_freq = int(ctx.get("last_suggested_freq", 0) or 0)
            if last_freq >= freq:
                return
            ctx["last_suggested_freq"] = freq
            try:
                updated_row.context = json.dumps(ctx, ensure_ascii=False)[:4000]
                self.db.commit()
            except Exception:
                pass

            log_learning_event("suggestion.emit", {"user_id": self.user_id, "action": action, "frequency": freq})
            await get_event_bus().publish("suggestion.new", {"user_id": self.user_id, **suggestion})
        except Exception:
            return

