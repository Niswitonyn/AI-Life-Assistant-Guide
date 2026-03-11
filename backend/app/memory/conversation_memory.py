from typing import Dict, List

from sqlalchemy.orm import Session

from app.database.models import ConversationInteraction, ConversationMemory
from app.memory.memory_logger import get_memory_logger


logger = get_memory_logger()


class ConversationMemoryStore:
    """
    Conversation persistence for both role-based context and full turn history.
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"

    def save_message(self, role: str, content: str, *, source: str = "chat") -> None:
        row = ConversationMemory(user_id=self.user_id, role=role, content=content, source=(source or "chat"))
        self.db.add(row)
        self.db.commit()

    def store_message(
        self,
        user_message: str,
        assistant_response: str,
        session_id: str = "default",
        *,
        source: str = "chat",
    ) -> int:
        session_value = (session_id or "").strip() or "default"
        row = ConversationInteraction(
            user_id=self.user_id,
            session_id=session_value,
            user_message=(user_message or "").strip(),
            assistant_response=(assistant_response or "").strip(),
            source=(source or "chat"),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        logger.info("memory stored | type=conversation | user_id=%s | interaction_id=%s", self.user_id, row.id)
        return row.id

    def get_recent_context(self, limit: int = 10) -> List[Dict[str, str]]:
        messages = (
            self.db.query(ConversationMemory)
            .filter(ConversationMemory.user_id == self.user_id)
            .order_by(ConversationMemory.id.desc())
            .limit(max(1, limit))
            .all()
        )
        messages.reverse()
        return [{"role": m.role, "content": m.content} for m in messages]

    def get_recent_context_from_interactions(self, limit: int = 5) -> List[Dict[str, str]]:
        rows = (
            self.db.query(ConversationInteraction)
            .filter(ConversationInteraction.user_id == self.user_id)
            .order_by(ConversationInteraction.id.desc())
            .limit(max(1, limit))
            .all()
        )
        rows.reverse()

        context: List[Dict[str, str]] = []
        for row in rows:
            context.append({"role": "user", "content": row.user_message})
            context.append({"role": "assistant", "content": row.assistant_response})
        return context

    def get_conversation_history(self, limit: int = 50, session_id: str | None = None) -> List[Dict]:
        query = (
            self.db.query(ConversationInteraction)
            .filter(ConversationInteraction.user_id == self.user_id)
        )
        if session_id:
            query = query.filter(ConversationInteraction.session_id == session_id)

        rows = query.order_by(ConversationInteraction.id.desc()).limit(max(1, limit)).all()
        rows.reverse()
        logger.info("memory retrieved | type=conversation_history | user_id=%s | count=%s", self.user_id, len(rows))
        return [
            {
                "id": row.id,
                "user_message": row.user_message,
                "assistant_response": row.assistant_response,
                "session_id": row.session_id,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
            }
            for row in rows
        ]
