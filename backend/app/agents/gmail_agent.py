from __future__ import annotations

import base64
import re
import time
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

from app.agents.base_agent import BaseAgent
from app.ai.base_provider import BaseAIProvider
from app.ai.provider_factory import provider_factory
from app.config.paths import CREDENTIALS_FILE
from app.core.email_logs import log_email_event
from app.data.contact_manager import ContactManager
from app.database.db import SessionLocal
from app.database.models import TrackedSender
from app.services.email_ai_service import ensure_email_ai
from app.services.google_token_store import load_gmail_credentials, save_gmail_credentials


logger = logging.getLogger(__name__)


class GmailAgent(BaseAgent):
    name = "gmail_agent"
    description = "Gmail automation (read/search/draft/improve/send/track) for the authenticated user."

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
    ]

    _send_timestamps: dict[str, list[float]] = {}

    def __init__(self, user_id: str = "default", *, provider: BaseAIProvider | None = None):
        self.user_id = (user_id or "").strip() or "default"
        self.provider = provider

        self.credentials_path = str(CREDENTIALS_FILE)

        self.contacts = ContactManager()
        self.service = self.authenticate()

    def authenticate(self):
        if not Path(self.credentials_path).exists():
            raise FileNotFoundError(
                f"Google credentials file not found at: {self.credentials_path}\n"
                f"Please go to Settings and upload your credentials.json file from Google Cloud Console."
            )

        creds = load_gmail_credentials(self.user_id, scopes=self.SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                save_gmail_credentials(self.user_id, creds)
            else:
                raise PermissionError(
                    f"Gmail token is invalid for user '{self.user_id}'. Please re-connect Gmail in Settings."
                )

        return build("gmail", "v1", credentials=creds)

    # -------------------------
    # Core helpers
    # -------------------------

    def _rate_limit_send(self) -> None:
        now = time.time()
        window = 60.0
        limit = 5
        ts = self._send_timestamps.setdefault(self.user_id, [])
        ts[:] = [t for t in ts if now - t < window]
        if len(ts) >= limit:
            raise RuntimeError("Rate limit exceeded for sending email. Please wait a minute and try again.")
        ts.append(now)

    def _format_preview(self, *, to: str, subject: str, body: str) -> str:
        return (
            "📧 Ready to send email — please confirm:\n"
            f"To: {to}\n"
            f"Subject: {subject}\n"
            f"Body: {body}\n\n"
            "Say 'yes send it' to confirm or 'cancel' to discard."
        )

    def _extract_sender(self, msg_data: Dict[str, Any]) -> str:
        headers = msg_data.get("payload", {}).get("headers", [])
        for h in headers:
            if h.get("name") == "From":
                return h.get("value", "")
        return ""

    # -------------------------
    # Gmail API operations
    # -------------------------

    def get_email_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        try:
            msg_data = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id)
                .execute()
            )

            headers = msg_data.get("payload", {}).get("headers", [])
            subject = ""
            sender = ""
            for h in headers:
                if h.get("name") == "Subject":
                    subject = h.get("value", "")
                if h.get("name") == "From":
                    sender = h.get("value", "")

            snippet = msg_data.get("snippet", "")
            return {"id": message_id, "subject": subject, "from": sender, "snippet": snippet}
        except Exception as e:
            logger.exception("Error getting email by id: %s", e)
            return None

    def read_inbox(self, limit: int = 5) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 20))
        try:
            results = (
                self.service.users()
                .messages()
                .list(userId="me", maxResults=limit)
                .execute()
            )
            messages = results.get("messages", [])
            emails: List[Dict[str, Any]] = []
            for msg in messages:
                item = self.get_email_by_id(msg.get("id", ""))
                if not item:
                    continue
                emails.append(item)

                # Auto-save contact from sender
                if item.get("from"):
                    self.contacts.add_from_sender(item["from"])
            return emails
        except Exception as e:
            logger.exception("Error reading inbox: %s", e)
            return []

    def get_latest_email(self) -> Optional[Dict[str, Any]]:
        emails = self.read_inbox(limit=1)
        return emails[0] if emails else None

    def search_email(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []
        limit = max(1, min(int(limit), 20))
        try:
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=q, maxResults=limit)
                .execute()
            )
            messages = results.get("messages", [])
            out: List[Dict[str, Any]] = []
            for msg in messages:
                item = self.get_email_by_id(msg.get("id", ""))
                if item:
                    out.append(item)
            return out
        except Exception as e:
            logger.exception("Error searching emails: %s", e)
            return []

    def send_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        to = self._resolve_recipient(to)
        if not self._is_valid_email(to):
            raise ValueError("Invalid recipient email address.")
        self._rate_limit_send()
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_message = {"raw": raw}

        self.service.users().messages().send(userId="me", body=send_message).execute()
        log_email_event("email_sent", {"user_id": self.user_id, "to": to, "subject": subject})
        return {"to": to, "subject": subject, "status": "sent"}

    def _resolve_recipient(self, to: str) -> str:
        to = (to or "").strip()
        if "@" in to:
            return to
        contacts = self.contacts.load_contacts()
        return contacts.get(to.strip().lower(), to)

    def _is_valid_email(self, value: str) -> bool:
        value = (value or "").strip()
        return bool(re.match(r"^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$", value))

    # -------------------------
    # Tracking
    # -------------------------

    def track_sender(self, email: str) -> Dict[str, Any]:
        email = (email or "").strip().lower()
        if not email:
            raise ValueError("Missing sender email")
        if email != "*" and not self._is_valid_email(email):
            # Try to resolve contact nicknames.
            email = self._resolve_recipient(email).strip().lower()
        if email != "*" and not self._is_valid_email(email):
            raise ValueError("Invalid sender email address.")

        db = SessionLocal()
        try:
            existing = (
                db.query(TrackedSender)
                .filter(TrackedSender.user_id == self.user_id, TrackedSender.email == email)
                .first()
            )
            if not existing:
                db.add(TrackedSender(user_id=self.user_id, email=email))
                db.commit()
            log_email_event("sender_tracked", {"user_id": self.user_id, "email": email})
            return {"email": email, "tracked": True}
        finally:
            db.close()

    # -------------------------
    # Agent interface
    # -------------------------

    async def execute(self, task: dict):
        task = task or {}
        action = (task.get("action") or "").strip()
        params = task.get("params") or {}
        task_text = task.get("text", "")

        # Supported actions (spec):
        # read_inbox, search_email, send_email, draft_email,
        # improve_email, track_sender, get_latest_email

        if action == "read_inbox":
            limit = int(params.get("limit", 5))
            emails = self.read_inbox(limit=limit)
            log_email_event("email_read", {"user_id": self.user_id, "count": len(emails)})
            return self._ok(task_text, action, {"emails": emails})

        if action == "get_latest_email":
            email = self.get_latest_email()
            log_email_event("email_latest", {"user_id": self.user_id, "found": bool(email)})
            return self._ok(task_text, action, {"email": email})

        if action == "search_email":
            query = (params.get("query") or "").strip()
            sender = (params.get("from") or "").strip()
            if sender:
                query = (query + " " if query else "") + f"from:{sender}"
            limit = int(params.get("limit", 5))
            emails = self.search_email(query, limit=limit)
            log_email_event("email_searched", {"user_id": self.user_id, "query": query, "count": len(emails)})
            return self._ok(task_text, action, {"query": query, "emails": emails})

        if action == "track_sender":
            email = (params.get("email") or params.get("from") or "").strip()
            if not email:
                return self._err(task_text, action, "Missing sender email to track.")
            try:
                data = self.track_sender(email)
                return self._ok(task_text, action, data)
            except Exception as e:
                return self._err(task_text, action, str(e))

        if action == "improve_email":
            text = (params.get("text") or "").strip()
            if not text:
                return self._err(task_text, action, "Missing email text to improve.")
            provider = self.provider or provider_factory.get_provider()
            ai = ensure_email_ai(provider)
            if not ai:
                return self._err(task_text, action, "AI provider not configured.")
            improved = await ai.improve_email(text)
            log_email_event("email_improved", {"user_id": self.user_id})
            to = (params.get("to") or "").strip()
            subject = (params.get("subject") or "").strip()
            if to and subject:
                preview = self._format_preview(to=to, subject=subject, body=improved)
                return self._needs_confirmation(
                    task_text,
                    action,
                    {"improved": improved, "preview": preview, "to": to, "subject": subject, "body": improved},
                )
            return self._ok(task_text, action, {"improved": improved})

        if action == "draft_email":
            to = (params.get("to") or "").strip()
            topic = (params.get("topic") or "").strip()
            if not to or not topic:
                return self._err(task_text, action, "Missing 'to' or 'topic'.")
            provider = self.provider or provider_factory.get_provider()
            ai = ensure_email_ai(provider)
            if not ai:
                return self._err(task_text, action, "AI provider not configured.")
            draft = await ai.draft_email(to=to, topic=topic)
            preview = self._format_preview(to=to, subject=draft["subject"], body=draft["body"])
            log_email_event("email_draft_generated", {"user_id": self.user_id, "to": to, "topic": topic})
            return self._needs_confirmation(task_text, action, {"preview": preview, "to": to, "subject": draft["subject"], "body": draft["body"]})

        if action == "send_email":
            to = (params.get("to") or "").strip()
            subject = (params.get("subject") or "Message from Jarvis").strip()
            body = (params.get("body") or "").strip()
            if not to:
                return self._err(task_text, action, "Missing 'to' address.")
            preview = self._format_preview(to=to, subject=subject, body=body)
            return self._needs_confirmation(task_text, action, {"preview": preview, "to": to, "subject": subject, "body": body})

        return self._err(task_text, action, f"Unsupported action: {action}")

    def _ok(self, task_text: str, action: str, data: Dict[str, Any]):
        return {"status": "success", "agent": self.name, "action": action, "task": task_text, "data": data, "result": data}

    def _needs_confirmation(self, task_text: str, action: str, data: Dict[str, Any]):
        return {"status": "needs_confirmation", "agent": self.name, "action": action, "task": task_text, "data": data, "result": data}

    def _err(self, task_text: str, action: str, error: str):
        return {"status": "error", "agent": self.name, "action": action, "task": task_text, "data": None, "result": None, "error": error}
