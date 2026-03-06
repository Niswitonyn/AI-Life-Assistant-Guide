from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.database.base import Base

# -----------------------------------------
# Database Engine
# -----------------------------------------

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite
)

# -----------------------------------------
# Session Local
# -----------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# -----------------------------------------
# Dependency (FastAPI)
# -----------------------------------------

def get_db():
    """
    Dependency to get DB session.
    Automatically closes after request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
