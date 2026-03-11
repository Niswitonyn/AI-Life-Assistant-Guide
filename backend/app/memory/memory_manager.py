import re
from typing import Dict, List

from sqlalchemy.orm import Session

from app.database.models import Contact, Memory
from app.memory.conversation_memory import ConversationMemoryStore
from app.memory.long_term_memory import LongTermMemory
from app.memory.semantic_memory import SemanticMemory
from app.memory.short_term_memory import ShortTermMemory


class MemoryManager:
    """
    Central memory controller orchestrating all memory types.
    """

    _short_term = ShortTermMemory(max_items=30)

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"

        self.short_term = self._short_term
        self.conversation = ConversationMemoryStore(db, self.user_id)
        self.long_term = LongTermMemory(db, self.user_id)
        self.semantic = SemanticMemory(db, self.user_id)

    def save_conversation(self, role: str, message: str, *, source: str = "chat") -> None:
        text = (message or "").strip()
        if not text:
            return
        self.conversation.save_message(role=role, content=text, source=source)
        self.short_term.push(self.user_id, role=role, content=text)

    def store_interaction(
        self,
        user_message: str,
        assistant_response: str,
        session_id: str = "default",
        *,
        source: str = "chat",
    ) -> int:
        return self.conversation.store_message(user_message, assistant_response, session_id=session_id, source=source)

    def get_recent_conversation(self, limit: int = 10) -> List[Dict[str, str]]:
        return self.conversation.get_recent_context(limit=limit)

    def add_memory(self, content: str, category: str = "general") -> int:
        memory = Memory(user_id=self.user_id, content=content, category=category)
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory.id

    def get_memories(self):
        return (
            self.db.query(Memory)
            .filter(Memory.user_id == self.user_id)
            .all()
        )

    def add_contact(self, name: str, email: str):
        contact = Contact(user_id=self.user_id, name=name, email=email)
        self.db.add(contact)
        self.db.commit()

    def get_contacts(self):
        return (
            self.db.query(Contact)
            .filter(Contact.user_id == self.user_id)
            .all()
        )

    def find_contact(self, name: str):
        return (
            self.db.query(Contact)
            .filter(
                Contact.user_id == self.user_id,
                Contact.name.ilike(f"%{name}%")
            )
            .first()
        )

    def clear_all(self):
        self.db.query(Memory).filter(Memory.user_id == self.user_id).delete()
        self.db.query(Contact).filter(Contact.user_id == self.user_id).delete()
        self.db.commit()
        self.short_term.clear(self.user_id)

    def importance_score_for(self, text: str, tags: List[str]) -> int:
        t = (text or "").lower()
        tag_set = {x.lower() for x in (tags or [])}

        if {"preference", "personal", "profile"}.intersection(tag_set):
            return 9
        if any(x in t for x in ["my favorite", "i prefer", "my name is", "i live in", "my email"]):
            return 9
        if any(x in t for x in ["building", "working on", "project", "goal"]):
            return 7
        if any(x in t for x in ["today", "tomorrow", "for now", "temporary"]):
            return 3
        return 5

    def learn_from_message(self, user_text: str, assistant_text: str = "") -> List[int]:
        text = (user_text or "").strip()
        if not text:
            return []

        learned_ids: List[int] = []
        detections: List[Dict[str, object]] = []

        lower = text.lower()
        if "my favorite language is" in lower:
            value = text.split("is", 1)[-1].strip(" .")
            detections.append({"content": f"favorite_language={value}", "tags": ["preference", "language"]})
        if "my name is" in lower:
            value = re.split(r"my name is", text, flags=re.IGNORECASE)[-1].strip(" .")
            detections.append({"content": f"name={value}", "tags": ["personal", "profile"]})
        if "i live in" in lower:
            value = re.split(r"i live in", text, flags=re.IGNORECASE)[-1].strip(" .")
            detections.append({"content": f"location={value}", "tags": ["personal", "location"]})
        if "i am building" in lower or "i'm building" in lower:
            value = text.strip(" .")
            detections.append({"content": f"project={value}", "tags": ["project", "goal"]})
        if "i like" in lower:
            value = re.split(r"i like", text, flags=re.IGNORECASE)[-1].strip(" .")
            detections.append({"content": f"likes={value}", "tags": ["preference"]})

        for item in detections:
            content = str(item.get("content") or "").strip()
            tags = list(item.get("tags") or [])
            importance = self.importance_score_for(content, tags)
            sensitive = any(tag in {"personal", "profile"} for tag in tags)
            long_term_id = self.long_term.store_fact(
                content=content,
                tags=tags,
                importance_score=importance,
                sensitive=sensitive,
            )
            self.semantic.store_semantic_memory(
                content=content,
                tags=tags,
                importance_score=importance,
                memory_ref_id=long_term_id,
            )
            learned_ids.append(long_term_id)

        return learned_ids

    def build_context(self, query: str, *, recent_limit: int = 10, semantic_limit: int = 5, long_term_limit: int = 5) -> Dict[str, List[Dict]]:
        recent = self.conversation.get_recent_context(limit=recent_limit)
        semantic = self.semantic.search_related_memory(query=query, limit=semantic_limit)
        long_term = self.long_term.get_memories(limit=long_term_limit)
        return {
            "recent_conversation": recent,
            "semantic_memories": semantic,
            "long_term_memories": long_term,
        }
