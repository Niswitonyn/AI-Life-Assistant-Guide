from sqlalchemy.orm import Session
from app.database.models import ConversationMemory


class ConversationManager:
    """
    Handles saving and retrieving conversation memory.
    """

    @staticmethod
    def save_message(db: Session, role: str, content: str):
        memory = ConversationMemory(
            role=role,
            content=content,
        )
        db.add(memory)
        db.commit()

    @staticmethod
    def get_recent_messages(db: Session, limit: int = 10):
        messages = (
            db.query(ConversationMemory)
            .order_by(ConversationMemory.timestamp.desc())
            .limit(limit)
            .all()
        )

        # reverse so oldest first
        messages.reverse()

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
