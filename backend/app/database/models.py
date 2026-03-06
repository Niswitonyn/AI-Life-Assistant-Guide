from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
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
