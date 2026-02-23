from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime

from app.database.db import Base


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

    role = Column(String(50))  # user / assistant
    content = Column(Text)

    timestamp = Column(DateTime, default=datetime.utcnow)
