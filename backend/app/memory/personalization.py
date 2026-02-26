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

    def get_profile(self) -> dict:
        """
        Build latest personalization profile from stored system facts.
        """
        records = (
            self.db.query(ConversationMemory)
            .filter(ConversationMemory.role == "system")
            .order_by(ConversationMemory.id.asc())
            .all()
        )

        profile = {}
        for record in records:
            content = (record.content or "").strip()
            if ":" not in content:
                continue

            key, value = content.split(":", 1)
            key = key.strip()
            value = value.strip()

            if key and value:
                profile[key] = value

        return profile

    def save_fact(self, key: str, value: str):

        memory = ConversationMemory(
            role="system",
            content=f"{key}:{value}"
        )

        self.db.add(memory)
        self.db.commit()
