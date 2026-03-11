from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float
from datetime import datetime

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    password = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    """
    Task model for reminders and todo items.
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    completed = Column(Boolean, default=False)

    due_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConversationMemory(Base):
    """
    Stores conversation history for context memory.
    """

    __tablename__ = "conversation_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default")

    role = Column(String(50))  # user / assistant
    content = Column(Text)
    source = Column(String(32), default="chat")  # chat / voice

    timestamp = Column(DateTime, default=datetime.utcnow)


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    content = Column(Text)
    category = Column(String, default="general")
    created_at = Column(DateTime, default=datetime.utcnow)


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    name = Column(String)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrackedSender(Base):
    __tablename__ = "tracked_senders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default")
    email = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConversationInteraction(Base):
    """
    Stores complete user-assistant exchanges for durable conversation history.
    """

    __tablename__ = "conversation_interactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default")
    session_id = Column(String, index=True, default="default")
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    source = Column(String(32), default="chat")  # chat / voice
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class LongTermMemoryEntry(Base):
    """
    Persistent user facts and preferences with importance metadata.
    """

    __tablename__ = "long_term_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default")
    content = Column(Text, nullable=False)
    tags = Column(String, nullable=True)
    importance_score = Column(Integer, default=5, index=True)
    is_sensitive = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)


class SemanticMemoryEntry(Base):
    """
    Embedding-backed memory records for semantic retrieval.
    """

    __tablename__ = "semantic_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default")
    memory_ref_id = Column(Integer, nullable=True, index=True)
    content = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=False)
    tags = Column(String, nullable=True)
    importance_score = Column(Integer, default=5, index=True)
    similarity_hint = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Document(Base):
    """
    Uploaded document metadata for the personal knowledge system.
    """

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default")

    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    size_bytes = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    upload_time = Column(DateTime, default=datetime.utcnow, index=True)


class UserBehavior(Base):
    """
    Usage statistics for self-learning behavior.
    """

    __tablename__ = "user_behavior"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default")
    action = Column(String, index=True, nullable=False)
    frequency = Column(Integer, default=0, index=True)
    last_used = Column(DateTime, default=datetime.utcnow, index=True)
    context = Column(Text, nullable=True)


class UserPreference(Base):
    """
    Persistent user preferences for personalization.
    """

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, default="default")
    key = Column(String, index=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)
