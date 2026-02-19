from sqlalchemy.orm import Session
from app.database.models import ConversationMemory


class PersonalizationEngine:
    """
    Extracts personal info from conversations.
    """

    def __init__(self, db: Session):
        self.db = db

    def process_user_text(self, text: str):

        text_lower = text.lower()

        # Detect name
        if "my name is" in text_lower:
            name = text_lower.split("my name is")[-1].strip()
            self.save_fact("name", name)

    def save_fact(self, key: str, value: str):

        memory = ConversationMemory(
            role="system",
            content=f"{key}:{value}"
        )

        self.db.add(memory)
        self.db.commit()
