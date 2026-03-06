from sqlalchemy.orm import Session
from app.database.models import ConversationMemory


class ConversationManager:
    """
    Handles saving and retrieving conversation memory.
    """

    @staticmethod
    def save_message(db: Session, user_id: str, role: str, content: str):
        memory = ConversationMemory(
            user_id=user_id,
            role=role,
            content=content,
        )
        db.add(memory)
        db.commit()

    @staticmethod
    def get_recent_messages(db: Session, user_id: str, limit: int = 10):
        messages = (
            db.query(ConversationMemory)
            .filter(ConversationMemory.user_id == user_id)
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
