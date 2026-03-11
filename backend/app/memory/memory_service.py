from sqlalchemy.orm import Session
from typing import List, Dict

from app.memory.memory_manager import MemoryManager


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
        MemoryManager(self.db, user_id=user_id).save_conversation(role=role, message=content)

    def store_message(self, user_id: str, user_message: str, assistant_response: str, session_id: str = "default") -> int:
        return MemoryManager(self.db, user_id=user_id).store_interaction(
            user_message=user_message,
            assistant_response=assistant_response,
            session_id=session_id,
        )

    # -------------------------
    # Get recent messages
    # -------------------------
    def get_recent_messages(self, user_id: str, limit: int = 10) -> List[Dict]:
        return MemoryManager(self.db, user_id=user_id).get_recent_conversation(limit=limit)
