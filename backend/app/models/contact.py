from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime

from app.database.base import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)

    # Link to user
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    name = Column(String)
    email = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)