from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.agents.gmail_agent import GmailAgent
from app.core.email_logs import log_email_event
from app.database.db import SessionLocal
from app.database.models import TrackedSender
from app.notifications.email_notifier import EmailNotifier


@dataclass
class _WatchKey:
    user_id: str
    sender: str


class EmailMonitor:
    """
    Inbox monitoring via polling.

    - Polls tracked senders (and optional wildcard '*') periodically
    - Detects new messages by message id changes
    - Triggers EmailNotifier
    """

    def __init__(self, notifier: EmailNotifier, *, interval_seconds: int = 60):
        self.notifier = notifier
        self.interval_seconds = max(10, int(interval_seconds))
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._last_seen: Dict[Tuple[str, str], str] = {}

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await self._task
            except Exception:
                pass

    async def _run_loop(self) -> None:
        log_email_event("email_monitor_started", {"interval_seconds": self.interval_seconds})
        while not self._stop.is_set():
            try:
                await self._poll_once()
            except Exception as e:
                log_email_event("email_monitor_error", {"error": str(e)}, error=str(e))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue
        log_email_event("email_monitor_stopped", {})

    async def _poll_once(self) -> None:
        db = SessionLocal()
        try:
            tracked: List[TrackedSender] = db.query(TrackedSender).all()
        finally:
            db.close()

        if not tracked:
            return

        # Group by user
        by_user: Dict[str, List[str]] = {}
        for row in tracked:
            by_user.setdefault(row.user_id, []).append(row.email)

        for user_id, senders in by_user.items():
            await self._poll_user(user_id, senders)

    async def _poll_user(self, user_id: str, senders: List[str]) -> None:
        try:
            agent = GmailAgent(user_id=user_id)
        except Exception:
            return

        # Wildcard means notify on any new inbox item.
        if "*" in senders:
            latest = agent.get_latest_email()
            if latest and latest.get("id"):
                key = (user_id, "*")
                last = self._last_seen.get(key)
                if last and last == latest["id"]:
                    return
                self._last_seen[key] = latest["id"]
                self.notifier.notify_new_email_data(
                    {
                        "sender": latest.get("from", ""),
                        "subject": latest.get("subject", ""),
                        "preview": latest.get("snippet", ""),
                        "message_id": latest.get("id", ""),
                        "user_id": user_id,
                    }
                )

        for sender in [s for s in senders if s and s != "*"]:
            query = f"from:{sender}"
            found = agent.search_email(query, limit=1)
            if not found:
                continue
            email = found[0]
            msg_id = email.get("id")
            if not msg_id:
                continue
            key = (user_id, sender)
            last = self._last_seen.get(key)
            if last and last == msg_id:
                continue
            self._last_seen[key] = msg_id
            self.notifier.notify_new_email_data(
                {
                    "sender": email.get("from", ""),
                    "subject": email.get("subject", ""),
                    "preview": email.get("snippet", ""),
                    "message_id": msg_id,
                    "user_id": user_id,
                    "tracked_sender": sender,
                }
            )


def create_email_monitor(notifier: EmailNotifier) -> EmailMonitor:
    interval = int(os.getenv("EMAIL_MONITOR_INTERVAL_SECONDS", "60").strip() or "60")
    return EmailMonitor(notifier, interval_seconds=interval)

