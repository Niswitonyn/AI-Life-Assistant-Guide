from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

from app.database.base import Base


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)

    content = Column(Text)
    category = Column(String, default="general")

    created_at = Column(DateTime, default=datetime.utcnow)