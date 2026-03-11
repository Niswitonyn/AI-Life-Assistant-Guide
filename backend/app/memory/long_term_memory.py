import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.database.models import LongTermMemoryEntry
from app.memory.memory_logger import get_memory_logger
from app.security.encryption import encryption_manager


logger = get_memory_logger()


class LongTermMemory:
    """
    Persistent fact store with ranking and optional encryption.
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"

    def store_fact(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        importance_score: int = 5,
        sensitive: bool = False,
        ttl_days: Optional[int] = None,
    ) -> int:
        normalized_score = min(10, max(1, int(importance_score or 5)))
        clean_content = (content or "").strip()
        if not clean_content:
            raise ValueError("content cannot be empty")

        expires_at = None
        if ttl_days is not None and ttl_days > 0:
            expires_at = datetime.utcnow() + timedelta(days=ttl_days)

        payload = encryption_manager.encrypt(clean_content) if sensitive else clean_content
        row = LongTermMemoryEntry(
            user_id=self.user_id,
            content=payload,
            tags=json.dumps(tags or []),
            importance_score=normalized_score,
            is_sensitive=bool(sensitive),
            expires_at=expires_at,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        logger.info(
            "memory stored | type=long_term | user_id=%s | id=%s | importance=%s",
            self.user_id,
            row.id,
            normalized_score,
        )
        return row.id

    def _decode_content(self, row: LongTermMemoryEntry) -> str:
        value = row.content or ""
        if row.is_sensitive and value:
            try:
                return encryption_manager.decrypt(value)
            except Exception:
                return "[encrypted-content-unavailable]"
        return value

    def get_memories(self, limit: int = 50) -> List[Dict]:
        rows = (
            self.db.query(LongTermMemoryEntry)
            .filter(LongTermMemoryEntry.user_id == self.user_id)
            .order_by(LongTermMemoryEntry.importance_score.desc(), LongTermMemoryEntry.id.desc())
            .limit(max(1, limit))
            .all()
        )

        return [
            {
                "id": row.id,
                "content": self._decode_content(row),
                "tags": json.loads(row.tags or "[]"),
                "importance_score": row.importance_score,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "is_sensitive": bool(row.is_sensitive),
            }
            for row in rows
        ]

    def delete_memory(self, memory_id: int) -> bool:
        row = (
            self.db.query(LongTermMemoryEntry)
            .filter(LongTermMemoryEntry.id == memory_id, LongTermMemoryEntry.user_id == self.user_id)
            .first()
        )
        if not row:
            return False

        self.db.delete(row)
        self.db.commit()
        logger.info("memory deleted | type=long_term | user_id=%s | id=%s", self.user_id, memory_id)
        return True

    def search_by_text(self, query: str, limit: int = 10) -> List[Dict]:
        q = (query or "").strip().lower()
        if not q:
            return []

        matched: List[Dict] = []
        for item in self.get_memories(limit=300):
            hay = f"{item.get('content', '')} {' '.join(item.get('tags') or [])}".lower()
            if q in hay:
                matched.append(item)

        matched.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
        return matched[: max(1, limit)]

    def cleanup_low_importance(self, min_importance_keep: int = 4, older_than_days: int = 30) -> int:
        threshold = datetime.utcnow() - timedelta(days=max(1, older_than_days))

        rows = (
            self.db.query(LongTermMemoryEntry)
            .filter(LongTermMemoryEntry.user_id == self.user_id)
            .filter(LongTermMemoryEntry.importance_score <= max(1, min_importance_keep))
            .filter(LongTermMemoryEntry.created_at < threshold)
            .all()
        )

        deleted = 0
        for row in rows:
            self.db.delete(row)
            deleted += 1

        self.db.commit()
        if deleted:
            logger.info(
                "memory deleted | type=long_term_cleanup | user_id=%s | count=%s",
                self.user_id,
                deleted,
            )
        return deleted
