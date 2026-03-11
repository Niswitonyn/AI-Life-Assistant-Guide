from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.ai.provider_factory import provider_factory
from app.agents.system_agent import SystemAgent
from app.automation.task_agent import TaskAgent
from app.core.task_planner import TaskPlanner
from app.core.reasoning_engine import ReasoningEngine
from app.memory.memory_manager import MemoryManager
from app.memory.personalization import PersonalizationEngine
from app.rag.retriever import retriever
from app.router.smart_router import SmartRouter
from app.services.event_bus import get_event_bus
from app.security.confirmation_service import confirmation_service
from app.security.security_logs import log_security_event
from app.security.security_manager import security_manager
from app.core.task_executor import TaskExecutor

logger = logging.getLogger(__name__)


class BrainController:
    """
    Unified controller for Chat + Voice input.

    Responsibilities:
    - Receive input from chat API and voice system
    - Send input to SmartRouter
    - Handle task planning + command chaining
    - Dispatch tasks to agents
    - Store results in memory (conversation + optional RAG + personalization)
    - Return a structured response and a display-friendly text reply
    """

    def __init__(
        self,
        db: Session,
        user_id: str = "default",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        is_authenticated: bool = False,
    ):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"

        self.provider_name = provider
        self.model = model
        self.is_authenticated = bool(is_authenticated)

        self.memory = MemoryManager(db, user_id=self.user_id)
        self.personalization = PersonalizationEngine(db)
        self.task_planner = TaskPlanner()

        try:
            self.provider = provider_factory.get_provider(provider_name=provider, model=model)
        except Exception:
            self.provider = None

        self.router = SmartRouter(
            user_id=self.user_id,
            provider=self.provider,
            task_planner=self.task_planner,
        )
        self.reasoning = ReasoningEngine(provider=self.provider)

        self.browser_agent = None
        self.system_agent = SystemAgent()
        self.task_agent = TaskAgent(db)
        self.file_agent = None

    async def handle_text(
        self,
        text: str,
        *,
        session_id: str = "default",
        save_to_memory: bool = True,
        update_rag: bool = True,
        update_personalization: bool = True,
        source: str = "chat",
    ) -> Dict[str, Any]:
        user_text = (text or "").strip()
        if not user_text:
            return self._structured_error("Empty message", task="(empty)")

        # Global confirmation flow for sensitive/critical operations.
        pending = confirmation_service.get_pending(self.user_id)
        if pending is not None:
            reply_kind = confirmation_service.classify_reply(user_text)
            if reply_kind == "cancel":
                confirmation_service.clear_pending(self.user_id)
                msg = "Cancelled."
                if save_to_memory:
                    self.memory.save_conversation("user", user_text, source=source)
                    self.memory.save_conversation("assistant", msg, source=source)
                    self.memory.store_interaction(user_text, msg, session_id=session_id, source=source)
                return self._structured_ok(msg, tasks=[])
            if reply_kind == "confirm":
                confirmation_service.clear_pending(self.user_id)
                # Execute the pending task as confirmed.
                confirmed_task = dict(pending.task or {})
                confirmed_task.setdefault("params", {})
                confirmed_task["params"]["_confirmed"] = True
                try:
                    await get_event_bus().publish(
                        "task_started",
                        {"user_id": self.user_id, "task": confirmed_task.get("text", ""), "action": confirmed_task.get("action"), "agent": confirmed_task.get("agent")},
                    )
                except Exception:
                    pass
                result = await self._dispatch(confirmed_task)
                try:
                    event_type = "task_completed" if result.get("status") == "success" else "task_error"
                    await get_event_bus().publish(
                        event_type,
                        {
                            "user_id": self.user_id,
                            "task": confirmed_task.get("text", ""),
                            "action": confirmed_task.get("action"),
                            "agent": confirmed_task.get("agent"),
                            "status": result.get("status"),
                            "error": result.get("error"),
                        },
                    )
                except Exception:
                    pass
                reply_text = self._format_task_reply([result])
                if save_to_memory:
                    self.memory.save_conversation("user", user_text, source=source)
                    self.memory.save_conversation("assistant", reply_text, source=source)
                    self.memory.store_interaction(user_text, reply_text, session_id=session_id, source=source)
                return self._structured_ok(reply_text, tasks=[result])

        if save_to_memory:
            self.memory.save_conversation("user", user_text, source=source)

        time_reply = self._handle_time_command(user_text)
        if time_reply:
            if save_to_memory:
                self.memory.save_conversation("assistant", time_reply, source=source)
                self.memory.store_interaction(user_text, time_reply, session_id=session_id, source=source)
            self._post_process(user_text, time_reply, update_rag, update_personalization)
            return self._structured_ok(time_reply, tasks=[])

        plan = await self.router.route(user_text)

        # Special confirmation flow: "send it" for email previews.
        confirm_result = await self._maybe_confirm_pending_email(user_text)
        if confirm_result is not None:
            reply_text, tasks = confirm_result
            structured = self._structured_ok(reply_text, tasks=tasks)
            if save_to_memory:
                self.memory.save_conversation("assistant", reply_text, source=source)
                self.memory.store_interaction(user_text, reply_text, session_id=session_id, source=source)
            self._post_process(user_text, reply_text, update_rag, update_personalization)
            return structured

        tasks_out: List[Dict[str, Any]] = []
        if plan.get("intent") != "chat" and plan.get("tasks"):
            executor = TaskExecutor(
                user_id=self.user_id,
                is_authenticated=self.is_authenticated,
                publish=get_event_bus().publish,
                dispatch=self._dispatch,
                apply_chain_context=self._apply_chain_context,
                update_chain_context=self._update_chain_context,
                memory_manager=self.memory,
            )
            summary = await executor.execute_tasks(plan["tasks"])
            if summary.status == "needs_confirmation":
                return self._structured_needs_confirmation(summary.confirm_task or plan["tasks"][0], result={"prompt": summary.prompt})

            tasks_out = summary.tasks
            reply_text = self._format_task_reply(tasks_out)
            structured = self._structured_ok(reply_text, tasks=tasks_out, status=summary.status)
            if save_to_memory:
                self.memory.save_conversation("assistant", reply_text, source=source)
                self.memory.store_interaction(user_text, reply_text, session_id=session_id, source=source)
            self._post_process(user_text, reply_text, update_rag, update_personalization)
            return structured

        # Reasoning layer: try to turn ambiguous/complex messages into an executable plan.
        try:
            context_bundle = self.memory.build_context(user_text, recent_limit=10, semantic_limit=5, long_term_limit=5)
            try:
                from app.learning.behavior_tracker import BehaviorTracker

                bt = BehaviorTracker(self.db, self.user_id)
                context_bundle["behavior"] = {"most_used_app": bt.most_used_app()}
            except Exception:
                context_bundle["behavior"] = {}
            analysis = await self.reasoning.analyze_intent(user_text, context_bundle)
            rewritten = (analysis.get("rewritten") or "").strip()
            clarification = (analysis.get("clarification") or "").strip()
            confidence = float(analysis.get("confidence") or 0.0)

            if clarification and confidence < 0.62:
                return self._structured_ok(clarification, tasks=[])

            if rewritten and bool(analysis.get("should_execute")) and confidence >= 0.62:
                routed = await self.router.route(rewritten)
                if routed.get("tasks"):
                    executor = TaskExecutor(
                        user_id=self.user_id,
                        is_authenticated=self.is_authenticated,
                        publish=get_event_bus().publish,
                        dispatch=self._dispatch,
                        apply_chain_context=self._apply_chain_context,
                        update_chain_context=self._update_chain_context,
                        memory_manager=self.memory,
                    )
                    summary = await executor.execute_tasks(routed["tasks"])
                    if summary.status == "needs_confirmation":
                        return self._structured_needs_confirmation(summary.confirm_task or routed["tasks"][0], result={"prompt": summary.prompt})
                    tasks_out = summary.tasks
                    reply_text = self._format_task_reply(tasks_out)
                    structured = self._structured_ok(reply_text, tasks=tasks_out, status=summary.status)
                    if save_to_memory:
                        self.memory.save_conversation("assistant", reply_text, source=source)
                        self.memory.store_interaction(user_text, reply_text, session_id=session_id, source=source)
                    self._post_process(user_text, reply_text, update_rag, update_personalization)
                    return structured
        except Exception:
            pass

        # Fallback: LLM chat with memory/RAG/personalization context.
        reply_text = await self._chat_fallback(user_text)
        structured = self._structured_ok(reply_text, tasks=[])
        if save_to_memory:
            self.memory.save_conversation("assistant", reply_text, source=source)
            self.memory.store_interaction(user_text, reply_text, session_id=session_id, source=source)
        self._post_process(user_text, reply_text, update_rag, update_personalization)
        return structured

    async def _chat_fallback(self, latest_user_message: str) -> str:
        if not self.provider:
            return "I’m not configured with an AI provider yet. Please set one in Settings."

        context_bundle = self.memory.build_context(latest_user_message, recent_limit=10, semantic_limit=5, long_term_limit=5)
        past_messages = context_bundle.get("recent_conversation", [])

        doc_hits = retriever.search(
            query=latest_user_message,
            top_k=5,
            filters={"user_id": self.user_id, "kind": "document_chunk"},
        )
        rag_prompt = self._build_rag_prompt(doc_hits)
        semantic_prompt = self._build_semantic_prompt(context_bundle.get("semantic_memories", []))
        long_term_prompt = self._build_long_term_prompt(context_bundle.get("long_term_memories", []))

        profile = self.personalization.get_profile(self.user_id)
        profile_prompt = self._build_profile_prompt(profile)

        system_prompt = {
            "role": "system",
            "content": (
                "You are Jarvis, a highly intelligent personal AI assistant. "
                "You are helpful, concise, polite, and slightly witty. "
                "You remember user preferences and personalize responses. "
                "Always aim to assist efficiently."
            ),
        }

        messages: List[Dict[str, str]] = [system_prompt]
        if profile_prompt:
            messages.append(profile_prompt)
        if long_term_prompt:
            messages.append(long_term_prompt)
        if semantic_prompt:
            messages.append(semantic_prompt)
        if rag_prompt:
            messages.append(rag_prompt)
        messages += past_messages
        messages.append({"role": "user", "content": latest_user_message})

        try:
            return await self.provider.generate_response(messages)
        except Exception as e:
            logger.exception("LLM fallback failed: %s", e)
            return "I had trouble reaching the AI provider. Please try again."

    async def _dispatch(self, task: Dict[str, Any]) -> Dict[str, Any]:
        action = task.get("action")
        params = task.get("params") or {}
        agent = task.get("agent") or "unknown"

        try:
            # Gmail automation
            if action in {"read_inbox", "search_email", "send_email", "draft_email", "improve_email", "track_sender", "get_latest_email"}:
                from app.agents.gmail_agent import GmailAgent

                try:
                    if action == "improve_email" and not (params.get("text") or "").strip():
                        extracted = self._extract_last_pending_email()
                        if extracted:
                            params["text"] = extracted.get("body", "")
                            params.setdefault("to", extracted.get("to", ""))
                            params.setdefault("subject", extracted.get("subject", ""))
                            task["params"] = params

                    gmail = GmailAgent(user_id=self.user_id, provider=self.provider)
                    return await gmail.execute(task)
                except Exception:
                    msg = (
                        "I could not access Gmail. "
                        "Please connect Google in Settings and ensure required scopes are enabled."
                    )
                    return {"status": "error", "task": task.get("text", ""), "agent": "gmail_agent", "result": None, "error": msg}

            if action == "system_execute":
                # Legacy path: route to structured system agent if possible.
                return await self.system_agent.execute(
                    {"text": task.get("text", ""), "action": "open_application", "params": {"app": (params.get("command") or "").strip()}}
                )

            if action in {"open_application", "shutdown", "restart", "lock_screen", "volume_control", "open_folder"}:
                return await self.system_agent.execute(task)

            if action == "task_create":
                created = self.task_agent.create_task_from_text(params.get("text", ""))
                return self._structured_from_agent(task, ok=True, result={"title": created.title})

            # Lazily import agents that can require external config (Gmail)
            if action in {"gmail_inbox", "gmail_summarize"}:
                from app.agents.gmail_agent import GmailAgent

                gmail = GmailAgent(user_id=self.user_id)
                limit = int(params.get("limit", 5))
                emails = gmail.get_latest_emails(max_results=limit)
                if action == "gmail_inbox":
                    return self._structured_from_agent(task, ok=True, result={"emails": emails})
                # summarize
                summary = await self.router.summarize_emails(emails)
                return self._structured_from_agent(task, ok=True, result={"summary": summary, "emails": emails})

            if action == "calendar_upcoming":
                from app.agents.calendar_agent import CalendarAgent

                cal = CalendarAgent(user_id=self.user_id)
                limit = int(params.get("limit", 5))
                events = cal.get_upcoming_events(max_results=limit)
                return self._structured_from_agent(task, ok=True, result={"events": events})

            if action and action.startswith("browser_"):
                from app.agents.browser_agent import BrowserAgent

                if self.browser_agent is None:
                    self.browser_agent = BrowserAgent()
                return await self.browser_agent.execute(task)

            if action in {"find_file", "open_file", "create_folder", "delete_file", "list_files"}:
                from app.agents.file_agent import FileAgent

                if self.file_agent is None:
                    self.file_agent = FileAgent()
                return await self.file_agent.execute(task)

            if action in {"document_list", "document_summarize", "document_question"}:
                from app.agents.document_agent import DocumentAgent

                doc_agent = DocumentAgent(self.db, user_id=self.user_id, provider=self.provider)
                return await doc_agent.execute(task)

            return self._structured_error(f"Unknown action: {action}", task=task.get("text", ""))
        except Exception as e:
            # Gmail/Calendar auth is a common failure mode; keep message user-friendly.
            if action and action.startswith("gmail"):
                msg = "I could not access Gmail. Please connect Google in Settings and ensure required scopes are enabled."
            else:
                msg = str(e) or "Task failed"
            return {
                "status": "error",
                "task": task.get("text", ""),
                "agent": agent,
                "result": None,
                "error": msg,
            }

    def _extract_last_pending_email(self) -> Optional[Dict[str, str]]:
        recent = self.memory.get_recent_conversation(limit=12)
        pending_preview = None
        for msg in reversed(recent):
            content = msg.get("content", "")
            if "📧 Ready to send email" in content:
                pending_preview = content
                break
        if not pending_preview:
            return None

        to_val = subject_val = body_val = ""
        for line in pending_preview.splitlines():
            if line.startswith("To: "):
                to_val = line[len("To: "):].strip()
            elif line.startswith("Subject: "):
                subject_val = line[len("Subject: "):].strip()
            elif line.startswith("Body: "):
                body_val = line[len("Body: "):].strip()

        if not body_val:
            return None
        return {"to": to_val, "subject": subject_val, "body": body_val}

    def _handle_time_command(self, user_text: str) -> Optional[str]:
        from datetime import datetime

        lower = (user_text or "").strip().lower()
        if not lower:
            return None

        time_keywords = [
            "time",
            "what time",
            "current time",
            "time now",
            "date",
            "today date",
            "what date",
            "day today",
        ]
        if not any(k in lower for k in time_keywords):
            return None

        now = datetime.now().astimezone()
        time_part = now.strftime("%I:%M %p").lstrip("0")
        date_part = now.strftime("%A, %d %B %Y")
        tz_part = now.tzname() or "local timezone"
        return f"It is {time_part} on {date_part} ({tz_part})."

    async def _maybe_confirm_pending_email(self, user_text: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        lower = (user_text or "").strip().lower()
        if not lower:
            return None

        if any(phrase in lower for phrase in ["yes send it", "send it", "confirm send"]):
            recent = self.memory.get_recent_conversation(limit=8)
            pending_preview = None
            for msg in reversed(recent):
                content = msg.get("content", "")
                if "📧 Ready to send email" in content:
                    pending_preview = content
                    break
            if not pending_preview:
                return ("No pending email to send.", [])

            to_val = subject_val = body_val = ""
            for line in pending_preview.splitlines():
                if line.startswith("To: "):
                    to_val = line[len("To: "):].strip()
                elif line.startswith("Subject: "):
                    subject_val = line[len("Subject: "):].strip()
                elif line.startswith("Body: "):
                    body_val = line[len("Body: "):].strip()

            try:
                from app.agents.gmail_agent import GmailAgent
                from app.memory.memory_manager import MemoryManager

                GmailAgent(user_id=self.user_id, provider=self.provider).send_email(to=to_val, subject=subject_val, body=body_val)
                # Save a memory fact for future personalization/RAG.
                try:
                    MemoryManager(self.db, self.user_id).add_memory(
                        content=f"User emailed {to_val} about '{subject_val}'.",
                        category="email",
                    )
                except Exception:
                    pass
                return ("📧 Email sent successfully.", [{"status": "success", "task": "send_email_confirm", "agent": "gmail_agent", "result": {"to": to_val, "subject": subject_val}}])
            except Exception:
                return (
                    "I could not send the email. Please re-connect Gmail in Settings and try again.",
                    [{"status": "error", "task": "send_email_confirm", "agent": "gmail_agent", "result": None}],
                )

        if "cancel" in lower:
            return ("📧 Email cancelled — nothing was sent.", [{"status": "success", "task": "gmail_send_cancel", "agent": "gmail_agent", "result": {}}])

        return None

    def _apply_chain_context(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # Fill missing params based on previous tasks.
        action = task.get("action")
        params = dict(task.get("params") or {})

        if action in {"browser_search", "browser_download_images", "browser_collect_info"}:
            q = (params.get("query") or params.get("topic") or "").strip()
            if not q:
                q = (context.get("last_query") or "").strip()
            if action == "browser_collect_info":
                params["topic"] = q
            else:
                params["query"] = q

        if action == "improve_email":
            txt = (params.get("text") or "").strip()
            if not txt:
                txt = (context.get("last_email_body") or "").strip()
            params["text"] = txt
            if not params.get("to"):
                params["to"] = (context.get("last_email_to") or "").strip()
            if not params.get("subject"):
                params["subject"] = (context.get("last_email_subject") or "").strip()

        copied = dict(task)
        copied["params"] = params
        return copied

    def _update_chain_context(self, task: Dict[str, Any], result: Dict[str, Any], context: Dict[str, Any]) -> None:
        action = task.get("action")
        params = task.get("params") or {}
        if action in {"browser_search", "browser_download_images", "browser_collect_info"}:
            q = (params.get("query") or params.get("topic") or "").strip()
            if q:
                context["last_query"] = q
        if action in {"draft_email", "send_email"}:
            data = result.get("result") if isinstance(result, dict) else None
            if isinstance(data, dict):
                body = (data.get("body") or "").strip()
                if body:
                    context["last_email_body"] = body
                to_val = (data.get("to") or "").strip()
                if to_val:
                    context["last_email_to"] = to_val
                subject_val = (data.get("subject") or "").strip()
                if subject_val:
                    context["last_email_subject"] = subject_val

    def _format_task_reply(self, tasks: List[Dict[str, Any]]) -> str:
        if not tasks:
            return "Okay."

        lines: List[str] = []
        for t in tasks:
            status = t.get("status")
            action = (t.get("task") or "").strip() or (t.get("action") or "").strip()
            agent = t.get("agent")
            if status == "needs_confirmation":
                preview = (t.get("result") or {}).get("preview")
                if preview:
                    lines.append(preview)
                else:
                    lines.append("Action requires confirmation.")
                continue
            if status == "error":
                lines.append(f"Failed: {action} ({agent})")
                err = t.get("error")
                if err:
                    lines.append(str(err))
                continue

            # success
            res = t.get("result")
            if isinstance(res, dict) and res.get("message"):
                lines.append(str(res["message"]))
            elif isinstance(res, dict) and res.get("emails") and isinstance(res["emails"], list):
                emails = res["emails"]
                if not emails:
                    lines.append("No emails found in inbox.")
                else:
                    lines.append("Here are your latest inbox items:")
                    for i, item in enumerate(emails[:5], start=1):
                        if isinstance(item, dict):
                            sender = (item.get("from") or "").strip()
                            subject = (item.get("subject") or "").strip()
                            snippet = (item.get("snippet") or "").strip()
                            line = f"{i}. {sender} — {subject}"
                            if snippet:
                                line += f" — {snippet}"
                            lines.append(line)
                        else:
                            lines.append(f"{i}. {item}")
            elif isinstance(res, dict) and res.get("summary"):
                lines.append(str(res["summary"]))
            elif isinstance(res, dict) and res.get("events") and isinstance(res["events"], list):
                events = res["events"]
                if not events:
                    lines.append("No upcoming calendar events found.")
                else:
                    lines.append("Here are your upcoming events:")
                    for i, event in enumerate(events[:5], start=1):
                        summary = event.get("summary", "(No title)")
                        start = event.get("start", "")
                        lines.append(f"{i}. {summary} at {start}")
            elif isinstance(res, dict) and res.get("path"):
                lines.append(f"Path: {res['path']}")
            elif isinstance(res, dict) and isinstance(res.get("results"), list):
                results = res.get("results") or []
                if results:
                    lines.append("Matches:")
                    for i, p in enumerate(results[:5], start=1):
                        lines.append(f"{i}. {p}")
                else:
                    lines.append("No matches found.")
            elif isinstance(res, dict) and isinstance(res.get("items"), list):
                items = res.get("items") or []
                list_path = (res.get("path") or "").strip()
                if list_path:
                    lines.append(f"Listing: {list_path}")
                for i, item in enumerate(items[:10], start=1):
                    if isinstance(item, dict):
                        lines.append(f"{i}. {item.get('name')} ({item.get('type')})")
            elif isinstance(res, dict) and res.get("improved"):
                lines.append(str(res["improved"]))
            elif isinstance(res, dict) and res.get("email") and isinstance(res.get("email"), dict):
                email = res["email"]
                sender = (email.get("from") or "").strip()
                subject = (email.get("subject") or "").strip()
                snippet = (email.get("snippet") or "").strip()
                lines.append(f"Latest email: {sender} — {subject}")
                if snippet:
                    lines.append(snippet)
            elif isinstance(res, dict) and res.get("tracked"):
                lines.append(f"Tracking emails from: {res.get('email')}")
            elif isinstance(res, dict) and res.get("source") == "google" and isinstance(res.get("results"), list):
                results = res.get("results") or []
                query = res.get("query") or ""
                lines.append(f"Search results for: {query}".strip())
                for i, item in enumerate(results[:5], start=1):
                    title = (item.get("title") or "").strip()
                    link = (item.get("link") or "").strip()
                    if title and link:
                        lines.append(f"{i}. {title} — {link}")
            elif isinstance(res, dict) and "downloaded" in res and "path" in res:
                lines.append(f"Downloaded {res.get('downloaded')} images to: {res.get('path')}")
            elif isinstance(res, dict) and any(k in res for k in ["titles", "paragraphs", "links"]):
                titles_n = len(res.get("titles") or []) if isinstance(res.get("titles"), list) else 0
                paras_n = len(res.get("paragraphs") or []) if isinstance(res.get("paragraphs"), list) else 0
                links_n = len(res.get("links") or []) if isinstance(res.get("links"), list) else 0
                lines.append(f"Extracted {titles_n} titles, {paras_n} paragraphs, {links_n} links.")
            else:
                lines.append(f"Done: {action}")

        return "\n".join([ln for ln in lines if ln]).strip() or "Okay."

    def _post_process(
        self,
        user_text: str,
        reply_text: str,
        update_rag: bool,
        update_personalization: bool,
    ) -> None:
        if update_rag:
            try:
                retriever.add_text(user_text, metadata={"user_id": self.user_id, "role": "user", "kind": "chat"})
                retriever.add_text(reply_text, metadata={"user_id": self.user_id, "role": "assistant", "kind": "chat"})
            except Exception:
                pass
        if update_personalization:
            try:
                self.personalization.process_user_text(self.user_id, user_text)
            except Exception:
                pass
        try:
            self.memory.learn_from_message(user_text=user_text, assistant_text=reply_text)
        except Exception:
            pass

    def _build_profile_prompt(self, profile: Dict[str, str]) -> Optional[Dict[str, str]]:
        if not profile:
            return None
        lines = [f"{key}: {value}" for key, value in profile.items()]
        return {
            "role": "system",
            "content": "Known user profile facts (use for personalization when relevant):\n" + "\n".join(lines),
        }

    def _build_rag_prompt(self, hits: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        if not hits:
            return None
        context_lines: List[str] = []
        for idx, hit in enumerate(hits, start=1):
            snippet = (hit.get("text", "") or "").strip()
            meta = hit.get("metadata", {}) if isinstance(hit.get("metadata", {}), dict) else {}
            doc = meta.get("document_name") or meta.get("source") or ""
            chunk_idx = meta.get("chunk_index")
            prefix = f"{idx}."
            if doc:
                prefix = f"{idx}. [{doc}{'' if chunk_idx is None else f' chunk {chunk_idx}'}]"
            if snippet:
                context_lines.append(f"{prefix} {snippet}")
        if not context_lines:
            return None
        return {
            "role": "system",
            "content": "Relevant document context (use to answer the user; cite which excerpt you used if possible):\n" + "\n".join(context_lines),
        }

    def _build_semantic_prompt(self, hits: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        if not hits:
            return None
        lines: List[str] = []
        for idx, hit in enumerate(hits, start=1):
            text = (hit.get("content", "") or "").strip()
            if text:
                lines.append(f"{idx}. {text}")
        if not lines:
            return None
        return {
            "role": "system",
            "content": "Semantic memory matches from prior conversations:\n" + "\n".join(lines),
        }

    def _build_long_term_prompt(self, entries: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        if not entries:
            return None
        lines: List[str] = []
        for entry in entries:
            content = (entry.get("content", "") or "").strip()
            score = entry.get("importance_score", 0)
            if content:
                lines.append(f"- ({score}/10) {content}")
        if not lines:
            return None
        return {
            "role": "system",
            "content": "Long-term user facts and preferences:\n" + "\n".join(lines),
        }

    def _structured_ok(self, response_text: str, *, tasks: List[Dict[str, Any]], status: str = "success") -> Dict[str, Any]:
        return {
            "status": status,
            "response_text": response_text,
            "tasks": tasks,
        }

    def _structured_error(self, error: str, *, task: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "response_text": error,
            "tasks": [
                {
                    "status": "error",
                    "task": task,
                    "agent": "brain_controller",
                    "result": None,
                    "error": error,
                }
            ],
        }

    def _structured_needs_confirmation(self, task: Dict[str, Any], *, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "needs_confirmation",
            "task": task.get("text", ""),
            "agent": task.get("agent", "gmail_agent"),
            "action": task.get("action"),
            "result": result,
        }

    def _structured_from_agent(self, task: Dict[str, Any], *, ok: bool, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success" if ok else "error",
            "task": task.get("text", ""),
            "agent": task.get("agent", "unknown"),
            "action": task.get("action"),
            "result": result if ok else None,
            "error": None if ok else "Task returned no result",
        }
