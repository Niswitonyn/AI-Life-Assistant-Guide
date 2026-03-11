import json
import math
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.database.models import SemanticMemoryEntry
from app.memory.memory_logger import get_memory_logger
from app.rag.embeddings import embedder


logger = get_memory_logger()


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(len(a)):
        dot += a[i] * b[i]
        norm_a += a[i] * a[i]
        norm_b += b[i] * b[i]

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class SemanticMemory:
    """
    Embedding-based memory retrieval backed by SQLite.
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"

    def store_semantic_memory(
        self,
        content: str,
        tags: Optional[List[str]] = None,
        importance_score: int = 5,
        memory_ref_id: Optional[int] = None,
    ) -> int:
        text = (content or "").strip()
        if not text:
            raise ValueError("content cannot be empty")

        vector = embedder.embed(text)
        row = SemanticMemoryEntry(
            user_id=self.user_id,
            memory_ref_id=memory_ref_id,
            content=text,
            embedding_json=json.dumps(vector),
            tags=json.dumps(tags or []),
            importance_score=min(10, max(1, int(importance_score or 5))),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        logger.info("memory stored | type=semantic | user_id=%s | id=%s", self.user_id, row.id)
        return row.id

    def search_related_memory(self, query: str, limit: int = 5) -> List[Dict]:
        q = (query or "").strip()
        if not q:
            return []
        q_lower = q.lower()
        q_tokens = {token for token in q_lower.replace("_", " ").split() if len(token) > 2}

        qv = embedder.embed(q)
        rows = (
            self.db.query(SemanticMemoryEntry)
            .filter(SemanticMemoryEntry.user_id == self.user_id)
            .all()
        )

        scored: List[Dict] = []
        for row in rows:
            try:
                vec = json.loads(row.embedding_json or "[]")
            except Exception:
                continue

            similarity = _cosine_similarity(qv, vec)
            lexical_hit = q_lower in (row.content or "").lower() or q_lower in (row.tags or "").lower()
            content_tokens = {token for token in (row.content or "").lower().replace("_", " ").split() if len(token) > 2}
            overlap = bool(q_tokens.intersection(content_tokens)) if q_tokens and content_tokens else False
            if similarity <= 0 and not lexical_hit and not overlap:
                continue
            if (lexical_hit or overlap) and similarity < 0.15:
                similarity = 0.15

            scored.append(
                {
                    "id": row.id,
                    "memory_ref_id": row.memory_ref_id,
                    "content": row.content,
                    "tags": json.loads(row.tags or "[]"),
                    "importance_score": row.importance_score,
                    "similarity": similarity,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
            )

        scored.sort(
            key=lambda x: (
                x.get("similarity", 0.0),
                float(x.get("importance_score", 0) or 0),
            ),
            reverse=True,
        )
        results = scored[: max(1, limit)]

        logger.info("memory retrieved | type=semantic_search | user_id=%s | query=%s | count=%s", self.user_id, q, len(results))
        return results
