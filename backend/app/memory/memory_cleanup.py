import logging
import threading
import time

from app.database.db import SessionLocal
from app.database.models import LongTermMemoryEntry
from app.memory.memory_logger import get_memory_logger


logger = logging.getLogger(__name__)
memory_logger = get_memory_logger()


def run_memory_cleanup(older_than_days: int = 30, max_importance: int = 3) -> int:
    db = SessionLocal()
    try:
        removed = 0
        user_ids = [row[0] for row in db.query(LongTermMemoryEntry.user_id).distinct().all() if row[0]]
        from app.memory.long_term_memory import LongTermMemory

        for user_id in user_ids:
            removed += LongTermMemory(db=db, user_id=user_id).cleanup_low_importance(
                min_importance_keep=max_importance,
                older_than_days=older_than_days,
            )

        if removed:
            memory_logger.info("memory deleted | type=scheduled_cleanup | count=%s", removed)
        return removed
    finally:
        db.close()


class MemoryCleanupScheduler:
    """
    Periodic cleanup of low-importance, old memories.
    """

    def __init__(self, interval_seconds: int = 24 * 60 * 60, older_than_days: int = 30, max_importance: int = 3):
        self.interval_seconds = max(60, interval_seconds)
        self.older_than_days = older_than_days
        self.max_importance = max_importance
        self._stop_event = threading.Event()

    def start(self):
        logger.info("Memory cleanup scheduler started")
        while not self._stop_event.is_set():
            try:
                run_memory_cleanup(older_than_days=self.older_than_days, max_importance=self.max_importance)
            except Exception as exc:
                logger.warning("Memory cleanup cycle failed: %s", exc)
            self._stop_event.wait(timeout=self.interval_seconds)

    def stop(self):
        self._stop_event.set()
