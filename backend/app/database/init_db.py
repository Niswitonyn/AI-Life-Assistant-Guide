from app.database.db import engine
from app.database.base import Base
from app.database import models
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

        if "source" not in column_names:
            conn.execute(
                text("ALTER TABLE conversation_memory ADD COLUMN source VARCHAR DEFAULT 'chat'")
            )
            conn.execute(
                text("UPDATE conversation_memory SET source = 'chat' WHERE source IS NULL")
            )

        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_conversation_memory_user_id ON conversation_memory (user_id)"
            )
        )

        # Patch conversation_interactions similarly.
        i_columns = conn.execute(text("PRAGMA table_info(conversation_interactions)")).fetchall()
        i_names = {row[1] for row in i_columns}
        if "source" not in i_names:
            conn.execute(
                text("ALTER TABLE conversation_interactions ADD COLUMN source VARCHAR DEFAULT 'chat'")
            )
            conn.execute(
                text("UPDATE conversation_interactions SET source = 'chat' WHERE source IS NULL")
            )

        # Ensure documents table exists for the personal knowledge system.
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS documents ("
                "id INTEGER PRIMARY KEY,"
                "user_id VARCHAR DEFAULT 'default',"
                "filename VARCHAR NOT NULL,"
                "stored_path VARCHAR NOT NULL,"
                "size_bytes INTEGER DEFAULT 0,"
                "chunk_count INTEGER DEFAULT 0,"
                "upload_time DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_upload_time ON documents (upload_time)"))

        # Self-learning tables.
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS user_behavior ("
                "id INTEGER PRIMARY KEY,"
                "user_id VARCHAR DEFAULT 'default',"
                "action VARCHAR NOT NULL,"
                "frequency INTEGER DEFAULT 0,"
                "last_used DATETIME DEFAULT CURRENT_TIMESTAMP,"
                "context TEXT"
                ")"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_behavior_user_id ON user_behavior (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_behavior_action ON user_behavior (action)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_behavior_last_used ON user_behavior (last_used)"))

        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS user_preferences ("
                "id INTEGER PRIMARY KEY,"
                "user_id VARCHAR DEFAULT 'default',"
                "key VARCHAR NOT NULL,"
                "value TEXT,"
                "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_preferences_user_id ON user_preferences (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_preferences_key ON user_preferences (key)"))
