from sqlalchemy.orm import Session
from typing import List, Dict

from app.database.models import ConversationMemory


class MemoryService:
    """
    Handles saving and retrieving conversation memory.
    """

    def __init__(self, db: Session):
        self.db = db

    # -------------------------
    # Save message
    # -------------------------
    def save_message(self, user_id: str, role: str, content: str):
        msg = ConversationMemory(
            user_id=user_id,
            role=role,
            content=content
        )
        self.db.add(msg)
        self.db.commit()

    # -------------------------
    # Get recent messages
    # -------------------------
    def get_recent_messages(self, user_id: str, limit: int = 10) -> List[Dict]:
        messages = (
            self.db.query(ConversationMemory)
            .filter(ConversationMemory.user_id == user_id)
            .order_by(ConversationMemory.id.desc())
            .limit(limit)
            .all()
        )

        messages = list(reversed(messages))

        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
