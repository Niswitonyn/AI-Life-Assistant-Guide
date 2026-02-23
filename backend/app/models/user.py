from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    # Primary ID
    id = Column(Integer, primary_key=True, index=True)

    # Public user identifier (for multi‑user systems)
    user_id = Column(String, unique=True, index=True)

    # User info
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)

    # Security (optional — for login system)
    password = Column(String, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)