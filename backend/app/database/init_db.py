from app.database.db import engine, Base
from app.database import models


def init_db():
    """
    Initialize database and create all tables.
    """
    Base.metadata.create_all(bind=engine)
