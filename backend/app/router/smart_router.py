from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.ai.base_provider import BaseAIProvider
from app.core.task_planner import TaskPlanner


class SmartRouter:
    """
    SmartRouter turns user text into structured, executable task specs.

    Capabilities:
    - Intent classification (rule-based + optional LLM)
    - Agent mapping (action -> agent name)
    - Multi-command parsing (via TaskPlanner)
    """

    def __init__(
        self,
        user_id: str = "default",
        *,
        provider: BaseAIProvider | None = None,
        task_planner: TaskPlanner | None = None,
    ):
        self.user_id = (user_id or "").strip() or "default"
        self.provider = provider
        self.task_planner = task_planner or TaskPlanner()

        self._agent_for_action: Dict[str, str] = {
            "read_inbox": "gmail_agent",
            "search_email": "gmail_agent",
            "send_email": "gmail_agent",
            "draft_email": "gmail_agent",
            "improve_email": "gmail_agent",
            "track_sender": "gmail_agent",
            "get_latest_email": "gmail_agent",
            "calendar_upcoming": "calendar_agent",
            "browser_open": "browser_agent",
            "browser_search": "browser_agent",
            "browser_download_images": "browser_agent",
            "browser_collect_info": "browser_agent",
            "browser_visit": "browser_agent",
            "find_file": "file_agent",
            "open_file": "file_agent",
            "create_folder": "file_agent",
            "delete_file": "file_agent",
            "list_files": "file_agent",
            "open_folder": "system_agent",
            "open_application": "system_agent",
            "shutdown": "system_agent",
            "restart": "system_agent",
            "lock_screen": "system_agent",
            "volume_control": "system_agent",
            "task_create": "task_agent",
            "document_list": "document_agent",
            "document_summarize": "document_agent",
            "document_question": "document_agent",
        }

    async def route(self, text: str) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"intent": "chat", "tasks": []}

        planned = self.task_planner.plan(text)
        tasks: List[Dict[str, Any]] = []

        for t in planned:
            parsed = self._parse_single_clause(t.text)
            if not parsed:
                continue

            action = parsed["action"]
            tasks.append(
                {
                    "id": t.id,
                    "text": t.text,
                    "intent": parsed.get("intent") or self._intent_for_action(action),
                    "agent": self._agent_for_action.get(action, "unknown"),
                    "action": action,
                    "params": parsed.get("params", {}) or {},
                }
            )

        tasks = self._insert_dependencies(tasks)

        if tasks:
            overall_intent = tasks[0].get("intent") or "command"
            return {"intent": overall_intent, "tasks": tasks}

        # No rule-based tasks detected -> LLM classification (or chat default).
        intent_data = await self.classify(text)
        return {"intent": intent_data.get("intent", "chat"), "tasks": []}

    def _insert_dependencies(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Insert lightweight prerequisites when missing.

        Example: browser_search / browser_download_images should have browser_open (or open chrome) first.
        """
        if not tasks:
            return tasks

        browser_needs = {"browser_search", "browser_download_images", "browser_collect_info", "browser_visit"}
        first_need_idx = next((i for i, t in enumerate(tasks) if t.get("action") in browser_needs), None)
        if first_need_idx is None:
            return tasks

        def _has_browser_open_before(idx: int) -> bool:
            for j in range(0, idx):
                a = tasks[j].get("action")
                if a == "browser_open":
                    return True
                if a == "open_application":
                    app = ((tasks[j].get("params") or {}).get("app") or "").lower()
                    if "chrome" in app:
                        return True
            return False

        if not _has_browser_open_before(first_need_idx):
            max_id = max((int(t.get("id") or 0) for t in tasks), default=0)
            dep_task = {
                "id": max_id + 1,
                "text": "open chrome",
                "intent": "browser",
                "agent": self._agent_for_action.get("browser_open", "browser_agent"),
                "action": "browser_open",
                "params": {"url": "https://www.google.com"},
            }
            tasks = [dep_task] + tasks
        return tasks

    async def classify(self, text: str) -> Dict[str, Any]:
        lower = (text or "").lower()
        if any(w in lower for w in ["email", "mail", "inbox", "gmail", "send email", "write email", "read emails", "search emails", "reply", "summarize inbox"]):
            return {"intent": "email"}
        if any(w in lower for w in ["calendar", "schedule", "event", "upcoming"]):
            return {"intent": "calendar"}
        if any(w in lower for w in ["open ", "shutdown", "restart", "lock", "volume", "mute", "unmute"]):
            return {"intent": "system"}
        if any(w in lower for w in ["find file", "search file", "create folder"]):
            return {"intent": "file"}
        if any(w in lower for w in ["search", "download images", "images of", "open chrome"]):
            return {"intent": "browser"}
        if any(w in lower for w in ["document", "documents", "summarize document", "list documents", "upload document"]):
            return {"intent": "rag"}

        if not self.provider:
            return {"intent": "chat"}

        prompt = f"""
You are an AI assistant that classifies user commands.

Return ONLY JSON.

Possible intents:
- system
- research
- file
- browser
- chat
- email
- calendar

Now classify:
{text}
"""

        try:
            reply = await self.provider.generate_response([{"role": "user", "content": prompt}])
            return json.loads(reply)
        except Exception:
            return {"intent": "chat"}

    async def summarize_emails(self, emails: List[str]) -> str:
        if not emails:
            return "No emails to summarize."
        if not self.provider:
            # Basic fallback without LLM.
            return "\n".join([f"- {e[:180]}" for e in emails[:5]])

        text_blob = "\n".join(emails[:10])
        prompt = f"""
Summarize these emails clearly.

{text_blob}

Give short bullet points.
"""

        try:
            reply = await self.provider.generate_response([{"role": "user", "content": prompt}])
            return reply.strip() if reply else "Could not summarize emails."
        except Exception:
            return "Could not summarize emails."

    # -------------------------
    # Parsing helpers
    # -------------------------

    def _intent_for_action(self, action: str) -> str:
        if action in {"read_inbox", "search_email", "send_email", "draft_email", "improve_email", "track_sender", "get_latest_email"}:
            return "email"
        if action.startswith("calendar_"):
            return "calendar"
        if action in {"find_file", "open_file", "create_folder", "delete_file", "list_files"}:
            return "file"
        if action.startswith("browser_"):
            return "browser"
        if action in {"open_application", "shutdown", "restart", "lock_screen", "volume_control", "open_folder"}:
            return "system"
        return "command"

    def _parse_send_email_command(self, text: str) -> Optional[Dict[str, str]]:
        lower = (text or "").lower().strip()
        trigger = "send email to "
        if not lower.startswith(trigger):
            return None

        raw = (text or "").strip()[len(trigger):].strip()
        raw_lower = raw.lower()
        if not raw:
            return None

        subject = "Message from Jarvis"
        body = "Hello,\n\nThis is a message sent by Jarvis.\n\nBest regards"

        if " saying " in raw_lower:
            to_part, body_part = raw.split(" saying ", 1)
            to_email = to_part.strip()
            body = (body_part or "").strip() or body
            if not to_email:
                return None
            return {"to": to_email, "subject": subject, "body": body}

        parts = raw.split(" subject ", 1)
        to_email = (parts[0] if parts else "").strip()
        if not to_email:
            return None

        if len(parts) > 1:
            tail = parts[1]
            if " body " in tail:
                subject_part, body_part = tail.split(" body ", 1)
                subject = (subject_part or "").strip() or subject
                body = (body_part or "").strip() or body
            else:
                subject = (tail or "").strip() or subject
        elif " about " in raw:
            to_part, topic = raw.split(" about ", 1)
            to_email = to_part.strip()
            subject = f"About {topic.strip()}" if topic.strip() else subject
            body = f"Hello,\n\nI am reaching out about {topic.strip()}.\n\nBest regards"

        return {"to": to_email, "subject": subject, "body": body}

    def _extract_after(self, text: str, marker: str) -> str:
        lower = text.lower()
        idx = lower.find(marker)
        if idx < 0:
            return ""
        return text[idx + len(marker):].strip()

    def _clean_value(self, value: str) -> str:
        cleaned = (value or "").strip(" ,;.")
        cleaned = re.sub(r"\s+(and|then)\s*$", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip(" ,;.")

    def _parse_single_clause(self, clause: str) -> Optional[Dict[str, Any]]:
        text = (clause or "").strip()
        lower = text.lower()
        if not lower:
            return None

        send_email = self._parse_send_email_command(text)
        if send_email:
            return {"intent": "email", "action": "send_email", "params": send_email}

        if any(key in lower for key in ["read my inbox", "check my inbox", "read my emails", "read emails"]):
            return {"intent": "email", "action": "read_inbox", "params": {"limit": 5}}

        if "summarize inbox" in lower:
            # Keep as read_inbox + summarize in BrainController/LLM if needed.
            return {"intent": "email", "action": "read_inbox", "params": {"limit": 5}}

        if lower.startswith("get latest email"):
            return {"intent": "email", "action": "get_latest_email", "params": {}}

        if lower.startswith("search emails from "):
            sender = self._clean_value(self._extract_after(text, "search emails from"))
            if sender:
                return {"intent": "email", "action": "search_email", "params": {"from": sender, "limit": 5}}

        if lower.startswith("track emails from "):
            sender = self._clean_value(self._extract_after(text, "track emails from"))
            if sender:
                return {"intent": "email", "action": "track_sender", "params": {"email": sender}}

        if "notify when new mail arrives" in lower:
            return {"intent": "email", "action": "track_sender", "params": {"email": "*"}}

        if lower.startswith("improve this email"):
            return {"intent": "email", "action": "improve_email", "params": {"text": ""}}

        if lower.startswith("open gmail"):
            return {"intent": "browser", "action": "browser_visit", "params": {"url": "https://mail.google.com/"}}

        if lower.startswith("write email to "):
            rest = self._extract_after(text, "write email to")
            # "write email to X about Y"
            if " about " in rest.lower():
                to_part, topic = re.split(r"\s+about\s+", rest, maxsplit=1, flags=re.IGNORECASE)
                to_val = self._clean_value(to_part)
                topic_val = self._clean_value(topic)
                if to_val and topic_val:
                    return {"intent": "email", "action": "draft_email", "params": {"to": to_val, "topic": topic_val}}

        if any(key in lower for key in ["calendar", "schedule", "upcoming events"]):
            return {"intent": "calendar", "action": "calendar_upcoming", "params": {"limit": 5}}

        if "download images of" in lower or "search images of" in lower:
            marker = "download images of" if "download images of" in lower else "search images of"
            topic = self._clean_value(self._extract_after(text, marker))
            return {"intent": "browser", "action": "browser_download_images", "params": {"query": topic, "limit": 10}}

        # If user says "download images" without a topic, let BrainController fill it from chain context.
        if lower.startswith("download images"):
            return {"intent": "browser", "action": "browser_download_images", "params": {"query": "", "limit": 10}}

        # "download cat images" / "download cats images"
        m = re.match(r"^download\s+(.+?)\s+images\b", lower)
        if m:
            topic = self._clean_value(m.group(1))
            return {"intent": "browser", "action": "browser_download_images", "params": {"query": topic, "limit": 10}}

        if lower.startswith("open chrome and search images of"):
            query = self._clean_value(self._extract_after(text, "open chrome and search images of"))
            if query:
                return {"intent": "browser", "action": "browser_download_images", "params": {"query": query, "limit": 10}}

        if lower.startswith("open chrome and search"):
            query = self._clean_value(self._extract_after(text, "open chrome and search"))
            if query:
                return {"intent": "browser", "action": "browser_search", "params": {"query": query, "limit": 5}}

        if lower.startswith("open chrome"):
            return {"intent": "browser", "action": "browser_open", "params": {}}

        if lower.startswith("search "):
            query = self._clean_value(self._extract_after(text, "search"))
            if query:
                return {"intent": "browser", "action": "browser_search", "params": {"query": query, "limit": 5}}

        if lower.startswith("open website ") or lower.startswith("open site "):
            marker = "open website" if lower.startswith("open website") else "open site"
            url = self._clean_value(self._extract_after(text, marker))
            if url:
                return {"intent": "browser", "action": "browser_visit", "params": {"url": url}}

        if lower.startswith("collect information about "):
            topic = self._clean_value(self._extract_after(text, "collect information about"))
            if topic:
                return {"intent": "browser", "action": "browser_collect_info", "params": {"topic": topic, "limit": 5}}

        if "find file" in lower or "search file" in lower:
            marker = "find file" if "find file" in lower else "search file"
            name = self._clean_value(self._extract_after(text, marker))
            if name:
                return {"intent": "file", "action": "find_file", "params": {"name": name}}

        if lower.startswith("open file "):
            name = self._clean_value(self._extract_after(text, "open file"))
            if name:
                return {"intent": "file", "action": "open_file", "params": {"name": name}}

        if lower.startswith("delete file "):
            name = self._clean_value(self._extract_after(text, "delete file"))
            if name:
                return {"intent": "file", "action": "delete_file", "params": {"name": name}}

        if lower.startswith("list files"):
            # Support: "list files", "list files in downloads"
            location = self._clean_value(self._extract_after(text, "list files"))
            location = location.lstrip("in ").strip()
            return {"intent": "file", "action": "list_files", "params": {"path": location or "documents", "limit": 50}}

        if "create folder called" in lower:
            folder_name = self._clean_value(self._extract_after(text, "create folder called"))
            if folder_name:
                return {"intent": "file", "action": "create_folder", "params": {"name": folder_name, "location": "documents"}}

        if lower.startswith("create folder "):
            folder_name = self._clean_value(self._extract_after(text, "create folder"))
            if folder_name:
                return {"intent": "file", "action": "create_folder", "params": {"name": folder_name, "location": "documents"}}

        if "open my documents" in lower or lower.strip() == "open documents":
            return {"intent": "system", "action": "open_folder", "params": {"path": str(Path.home() / "Documents")}}
        if "open my downloads" in lower or lower.strip() == "open downloads":
            return {"intent": "system", "action": "open_folder", "params": {"path": str(Path.home() / "Downloads")}}
        if "open my desktop" in lower:
            return {"intent": "system", "action": "open_folder", "params": {"path": str(Path.home() / "Desktop")}}
        if "open my pictures" in lower:
            return {"intent": "system", "action": "open_folder", "params": {"path": str(Path.home() / "Pictures")}}

        if lower.startswith("open "):
            app_name = self._clean_value(self._extract_after(text, "open"))
            if app_name and app_name not in {"my documents", "my downloads", "my desktop", "my pictures"}:
                if app_name.startswith("file "):
                    name = self._clean_value(self._extract_after(app_name, "file"))
                    return {"intent": "file", "action": "open_file", "params": {"name": name}}
                return {"intent": "system", "action": "open_application", "params": {"app": app_name}}

        # System actions: require explicit phrasing to reduce accidental triggers.
        if "shutdown computer" in lower or "shut down computer" in lower:
            return {"intent": "system", "action": "shutdown", "params": {}}
        if "restart computer" in lower or "reboot computer" in lower:
            return {"intent": "system", "action": "restart", "params": {}}
        if "lock screen" in lower or "lock the screen" in lower:
            return {"intent": "system", "action": "lock_screen", "params": {}}

        # Absolute-ish set: "set volume 35", "set volume to 35%"
        m = re.search(r"\bset\s+volume(?:\s+to)?\s+(\d{1,3})\s*%?\b", lower)
        if m:
            level = int(m.group(1))
            return {"intent": "system", "action": "volume_control", "params": {"mode": "set", "level": level}}

        if "volume up" in lower or "increase volume" in lower:
            return {"intent": "system", "action": "volume_control", "params": {"mode": "up", "steps": 6}}
        if "volume down" in lower or "decrease volume" in lower:
            return {"intent": "system", "action": "volume_control", "params": {"mode": "down", "steps": 6}}
        if "unmute volume" in lower or ("unmute" in lower and "volume" in lower):
            return {"intent": "system", "action": "volume_control", "params": {"mode": "unmute"}}
        if "mute volume" in lower or ("mute" in lower and "volume" in lower):
            return {"intent": "system", "action": "volume_control", "params": {"mode": "mute"}}

        if "remind me to" in lower or lower.startswith("add task") or lower.startswith("create task"):
            return {"intent": "task", "action": "task_create", "params": {"text": text}}

        if lower.strip() == "list documents" or "list my documents" in lower:
            return {"intent": "rag", "action": "document_list", "params": {}}

        if lower.startswith("summarize document "):
            name = self._clean_value(self._extract_after(text, "summarize document"))
            if name:
                return {"intent": "rag", "action": "document_summarize", "params": {"name": name}}

        if lower.startswith("summarize my "):
            name = self._clean_value(self._extract_after(text, "summarize my"))
            if name:
                return {"intent": "rag", "action": "document_summarize", "params": {"name": name}}

        if "what does the document say about" in lower:
            q = self._clean_value(self._extract_after(text, "what does the document say about"))
            if q:
                return {"intent": "rag", "action": "document_question", "params": {"question": q}}

        if lower.startswith("ask about document "):
            rest = self._clean_value(self._extract_after(text, "ask about document"))
            if rest:
                return {"intent": "rag", "action": "document_question", "params": {"question": rest}}

        return None
