from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config.settings import settings

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
# Base Model
# -----------------------------------------

Base = declarative_base()


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
