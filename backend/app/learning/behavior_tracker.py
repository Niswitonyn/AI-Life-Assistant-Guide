from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.database.models import UserBehavior
from app.learning.learning_logs import log_learning_event
from app.learning.user_preferences import UserPreferences


class BehaviorTracker:
    """
    Records lightweight behavior stats per user.
    """

    PREF_ENABLED = "behavior_tracking_enabled"

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"
        self.prefs = UserPreferences(db, self.user_id)

    def is_enabled(self) -> bool:
        raw = self.prefs.get(self.PREF_ENABLED, default="true")
        return str(raw).strip().lower() not in {"0", "false", "no", "off"}

    def record(self, action: str, *, context: Optional[Dict[str, Any]] = None) -> Optional[UserBehavior]:
        if not self.is_enabled():
            return None

        a = (action or "").strip()
        if not a:
            return None

        row = (
            self.db.query(UserBehavior)
            .filter(UserBehavior.user_id == self.user_id)
            .filter(UserBehavior.action == a)
            .first()
        )
        if row is None:
            row = UserBehavior(user_id=self.user_id, action=a, frequency=0)
            self.db.add(row)

        row.frequency = int(row.frequency or 0) + 1
        row.last_used = datetime.utcnow()
        if context is not None:
            try:
                row.context = json.dumps(context, ensure_ascii=False)[:4000]
            except Exception:
                row.context = None

        self.db.commit()
        log_learning_event("behavior.record", {"user_id": self.user_id, "action": a, "frequency": row.frequency})
        return row

    def top_actions(self, prefix: str, *, limit: int = 5) -> List[Tuple[str, int]]:
        p = (prefix or "").strip()
        q = self.db.query(UserBehavior).filter(UserBehavior.user_id == self.user_id)
        if p:
            q = q.filter(UserBehavior.action.like(f"{p}%"))
        rows = q.order_by(UserBehavior.frequency.desc()).limit(max(1, int(limit))).all()
        return [(r.action, int(r.frequency or 0)) for r in rows]

    def most_used_app(self) -> Optional[str]:
        rows = self.top_actions("open_app:", limit=1)
        if not rows:
            return None
        action, _ = rows[0]
        return action.split("open_app:", 1)[-1].strip() or None

