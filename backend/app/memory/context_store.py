from sqlalchemy.orm import Session
from app.memory.conversation import ConversationManager


class ContextStore:
    """
    Builds AI context from past memory.
    """

    @staticmethod
    def build_context(db: Session, new_messages: list):
        """
        Combine past memory + new user messages.
        """

        history = ConversationManager.get_recent_messages(db)

        return history + new_messages
