from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.database.models import UserPreference
from app.learning.learning_logs import log_learning_event


class UserPreferences:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"

    def get(self, key: str, default: Any = None) -> Any:
        k = (key or "").strip()
        if not k:
            return default
        row = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == self.user_id)
            .filter(UserPreference.key == k)
            .order_by(UserPreference.id.desc())
            .first()
        )
        if not row:
            return default
        return row.value

    def set(self, key: str, value: str | None) -> None:
        k = (key or "").strip()
        if not k:
            return
        row = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == self.user_id)
            .filter(UserPreference.key == k)
            .first()
        )
        if row is None:
            row = UserPreference(user_id=self.user_id, key=k, value=value or "")
            self.db.add(row)
        else:
            row.value = value or ""
            row.updated_at = datetime.utcnow()
        self.db.commit()
        log_learning_event("preference.set", {"user_id": self.user_id, "key": k})

    def as_dict(self) -> Dict[str, str]:
        rows = self.db.query(UserPreference).filter(UserPreference.user_id == self.user_id).all()
        out: Dict[str, str] = {}
        for r in rows:
            out[str(r.key)] = str(r.value or "")
        return out

    def reset(self) -> int:
        n = self.db.query(UserPreference).filter(UserPreference.user_id == self.user_id).delete()
        self.db.commit()
        log_learning_event("preference.reset", {"user_id": self.user_id, "count": int(n)})
        return int(n)

