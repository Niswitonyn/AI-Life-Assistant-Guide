from __future__ import annotations

import asyncio
from typing import Any, Dict

from app.core.email_logs import log_email_event
from app.services.event_bus import get_event_bus


class EmailNotifier:
    def __init__(self, gmail_agent=None, voice_assistant=None, ai_url=None):
        self.gmail_agent = gmail_agent
        self.voice_assistant = voice_assistant
        self.ai_url = ai_url

    def notify_new_email(self, message_id: str):
        if not self.gmail_agent:
            return

        try:
            message = self.gmail_agent.get_email_by_id(message_id)
            if not message:
                return

            self.notify_new_email_data(
                {
                    "sender": message.get("from", "Unknown sender"),
                    "subject": message.get("subject", "New Email"),
                    "preview": message.get("snippet", ""),
                    "message_id": message_id,
                }
            )
        except Exception as e:
            log_email_event("email_notify_failed", {"message_id": message_id}, error=str(e))

    def notify_new_email_data(self, data: Dict[str, Any]):
        sender = data.get("sender", "Unknown sender")
        subject = data.get("subject", "New Email")
        preview = data.get("preview", "")

        text = f"You received a new email from {sender}. Subject: {subject}"
        if preview:
            text = text + f" Preview: {str(preview)[:120]}"

        log_email_event("email_notification", {"sender": sender, "subject": subject})

        try:
            if self.voice_assistant:
                self.voice_assistant.speak(text)
        except Exception:
            pass

        # Publish to event bus for frontend consumption (SSE route).
        try:
            bus = get_event_bus()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(bus.publish("email.new", data))
            except RuntimeError:
                # No running loop in this thread: best-effort fire-and-forget.
                asyncio.run(bus.publish("email.new", data))
        except Exception:
            pass
