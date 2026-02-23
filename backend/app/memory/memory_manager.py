from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.conversation import Conversation
from app.models.contact import Contact


class MemoryManager:

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    # -------------------------
    # SAVE CONVERSATION
    # -------------------------
    def save_conversation(self, role: str, message: str):

        convo = Conversation(
            user_id=self.user_id,
            role=role,
            message=message
        )

        self.db.add(convo)
        self.db.commit()

    # -------------------------
    # GET RECENT CONVERSATION
    # -------------------------
    def get_recent_conversation(self, limit: int = 10):

        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == self.user_id)
            .order_by(Conversation.id.desc())
            .limit(limit)
            .all()
        )

    # -------------------------
    # SAVE MEMORY FACT
    # -------------------------
    def add_memory(self, content: str, category: str = "general"):

        memory = Memory(
            user_id=self.user_id,
            content=content,
            category=category
        )

        self.db.add(memory)
        self.db.commit()

    # -------------------------
    # GET MEMORIES
    # -------------------------
    def get_memories(self):

        return (
            self.db.query(Memory)
            .filter(Memory.user_id == self.user_id)
            .all()
        )

    # -------------------------
    # ADD CONTACT
    # -------------------------
    def add_contact(self, name: str, email: str):

        contact = Contact(
            user_id=self.user_id,
            name=name,
            email=email
        )

        self.db.add(contact)
        self.db.commit()

    # -------------------------
    # GET CONTACTS
    # -------------------------
    def get_contacts(self):

        return (
            self.db.query(Contact)
            .filter(Contact.user_id == self.user_id)
            .all()
        )

    # -------------------------
    # FIND CONTACT BY NAME
    # -------------------------
    def find_contact(self, name: str):

        return (
            self.db.query(Contact)
            .filter(
                Contact.user_id == self.user_id,
                Contact.name.ilike(f"%{name}%")
            )
            .first()
        )

    # -------------------------
    # CLEAR USER MEMORY (optional)
    # -------------------------
    def clear_all(self):

        self.db.query(Conversation).filter(
            Conversation.user_id == self.user_id
        ).delete()

        self.db.query(Memory).filter(
            Memory.user_id == self.user_id
        ).delete()

        self.db.query(Contact).filter(
            Contact.user_id == self.user_id
        ).delete()

        self.db.commit()