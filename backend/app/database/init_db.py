from app.database.db import engine, Base
from app.database import models
from app.models import user as user_model  # noqa: F401
from sqlalchemy import text


def init_db():
    """
    Initialize database and create all tables.
    """
    Base.metadata.create_all(bind=engine)

    # Lightweight schema patch for existing SQLite installs:
    # add conversation_memory.user_id if table was created before multi-user support.
    with engine.begin() as conn:
        columns = conn.execute(text("PRAGMA table_info(conversation_memory)")).fetchall()
        column_names = {row[1] for row in columns}

        if "user_id" not in column_names:
            conn.execute(
                text("ALTER TABLE conversation_memory ADD COLUMN user_id VARCHAR DEFAULT 'default'")
            )
            conn.execute(
                text("UPDATE conversation_memory SET user_id = 'default' WHERE user_id IS NULL")
            )

        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_conversation_memory_user_id ON conversation_memory (user_id)"
            )
        )
