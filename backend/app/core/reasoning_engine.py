from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.ai.base_provider import BaseAIProvider
from app.core.reasoning_logs import log_reasoning_event
from app.core.ttl_cache import TTLCache
from app.core.usage_stats import usage_stats


INTENTS = [
    "chat_conversation",
    "web_search",
    "browser_action",
    "system_control",
    "file_operation",
    "email_action",
    "document_question",
    "memory_query",
]


@dataclass(frozen=True)
class ReasoningResult:
    intent: str
    agent: str
    confidence: float
    should_execute: bool
    rewritten: Optional[str] = None
    clarification: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "agent": self.agent,
            "confidence": float(self.confidence),
            "should_execute": bool(self.should_execute),
            "rewritten": self.rewritten,
            "clarification": self.clarification,
        }


class ReasoningEngine:
    """
    Intent + action decision layer.

    Used when rule-based routing didn't produce executable tasks, or when input
    is ambiguous ("do that again", "download those images", etc.).
    """

    def __init__(self, *, provider: BaseAIProvider | None = None):
        self.provider = provider
        # Cache LLM classifications briefly to reduce repeat calls (voice/chat retries).
        self._llm_cache: TTLCache[str, ReasoningResult] = TTLCache(ttl_s=20.0, max_items=256)

    async def analyze_intent(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        text = (user_input or "").strip()
        ctx_msgs = list((context or {}).get("recent_conversation", []) or [])
        behavior = (context or {}).get("behavior") or {}

        heur = self._heuristic(text, ctx_msgs, behavior)
        if heur:
            log_reasoning_event("reasoning.heuristic", {"input": text, **heur.to_dict()})
            return heur.to_dict()

        # LLM fallback only if provider exists.
        if not self.provider:
            res = ReasoningResult(
                intent="chat_conversation",
                agent="chat",
                confidence=0.5,
                should_execute=False,
            )
            log_reasoning_event("reasoning.no_provider", {"input": text, **res.to_dict()})
            return res.to_dict()

        try:
            llm = await self._llm_classify(text, ctx_msgs)
            log_reasoning_event("reasoning.llm", {"input": text, **llm.to_dict()})
            return llm.to_dict()
        except Exception as e:
            res = ReasoningResult(intent="chat_conversation", agent="chat", confidence=0.4, should_execute=False)
            log_reasoning_event("reasoning.llm_failed", {"input": text, **res.to_dict()}, error=str(e))
            return res.to_dict()

    # -------------------------
    # Heuristics
    # -------------------------

    def _heuristic(self, text: str, recent: List[Dict[str, str]], behavior: Dict[str, Any]) -> Optional[ReasoningResult]:
        lower = text.lower()

        # Quick intent for obvious Q&A.
        if re.match(r"^(what is|who is|explain|define)\b", lower):
            return ReasoningResult("chat_conversation", "chat", 0.75, should_execute=False)

        # Memory query.
        if "what did i say" in lower or "show my history" in lower or "memory" in lower and "search" in lower:
            return ReasoningResult("memory_query", "memory", 0.72, should_execute=True, rewritten="show memory history")

        # Ambiguous browser follow-up: "download those images", "download them"
        if ("download" in lower and ("images" in lower or "them" in lower or "those" in lower)) or "download those" in lower:
            last_query = self._infer_last_web_query(recent)
            if last_query:
                usage_stats.bump("web_query", last_query)
                return ReasoningResult(
                    intent="browser_action",
                    agent="browser_agent",
                    confidence=0.78,
                    should_execute=True,
                    rewritten=f"download images of {last_query}",
                )
            return ReasoningResult(
                intent="browser_action",
                agent="browser_agent",
                confidence=0.45,
                should_execute=False,
                clarification="Which images should I download (what should I search for)?",
            )

        # Ambiguous system follow-up: "open it again", "do that again"
        if any(p in lower for p in ["do that again", "repeat that", "open it again", "again"]):
            last_open = self._infer_last_open_app(recent)
            if last_open:
                usage_stats.bump("app_open", last_open)
                return ReasoningResult(
                    intent="system_control",
                    agent="system_agent",
                    confidence=0.7,
                    should_execute=True,
                    rewritten=f"open {last_open}",
                )

        # "open browser" -> prefer most used app, default chrome
        if lower.strip() in {"open browser", "open the browser"}:
            preferred = (behavior.get("most_used_app") or "").strip().lower()
            if preferred:
                return ReasoningResult("system_control", "system_agent", 0.7, should_execute=True, rewritten=f"open {preferred}")
            return ReasoningResult("system_control", "system_agent", 0.62, should_execute=True, rewritten="open chrome")

        # "open the editor" -> map to most used app if it looks like an editor
        if lower.strip() in {"open the editor", "open editor"}:
            preferred = (behavior.get("most_used_app") or "").strip().lower()
            if preferred and any(x in preferred for x in ["code", "vscode", "notepad"]):
                return ReasoningResult("system_control", "system_agent", 0.7, should_execute=True, rewritten=f"open {preferred}")
            return ReasoningResult(
                "system_control",
                "system_agent",
                0.5,
                should_execute=False,
                clarification="Which editor should I open (VSCode, Notepad, ...)?",
            )

        # Document question phrasing.
        if any(w in lower for w in ["uploaded", "document", "pdf", "docx", "paper"]) and "summarize" in lower:
            return ReasoningResult("document_question", "document_agent", 0.72, should_execute=True, rewritten=text)
        if any(w in lower for w in ["what does", "according to", "in the document", "in the paper"]) and any(w in lower for w in ["document", "paper", "pdf"]):
            return ReasoningResult("document_question", "document_agent", 0.7, should_execute=True, rewritten=text)

        return None

    def _infer_last_web_query(self, recent: List[Dict[str, str]]) -> Optional[str]:
        # Find the most recent user clause that looks like a query.
        for msg in reversed(recent[-20:]):
            if (msg.get("role") or "").lower() != "user":
                continue
            t = (msg.get("content") or "").strip()
            if not t:
                continue
            m = re.search(r"\bsearch(?:\s+for)?\s+(.+)$", t, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip(" .")
            m = re.search(r"\b(download images of|images of)\s+(.+)$", t, flags=re.IGNORECASE)
            if m:
                return m.group(2).strip(" .")
        return None

    def _infer_last_open_app(self, recent: List[Dict[str, str]]) -> Optional[str]:
        for msg in reversed(recent[-20:]):
            if (msg.get("role") or "").lower() != "user":
                continue
            t = (msg.get("content") or "").strip()
            m = re.search(r"^\s*open\s+([a-z0-9 ._-]+)\s*$", t, flags=re.IGNORECASE)
            if m:
                app = m.group(1).strip().lower()
                if app not in {"documents", "downloads", "my documents", "my downloads"}:
                    return app
        return None

    # -------------------------
    # LLM
    # -------------------------

    async def _llm_classify(self, text: str, recent: List[Dict[str, str]]) -> ReasoningResult:
        cache_key = f"{text.strip().lower()[:600]}|h={hash(json.dumps(recent[-4:], ensure_ascii=False, sort_keys=True))}"
        cached = self._llm_cache.get(cache_key)
        if cached is not None:
            return cached

        # Keep context small and robust against prompt injection: pass only last few messages.
        history = [{"role": m.get("role"), "content": (m.get("content") or "")[:400]} for m in recent[-8:]]

        prompt = {
            "role": "user",
            "content": (
                "Classify the user's intent and decide whether to execute an automation command.\n"
                "Return ONLY JSON with keys: intent, agent, confidence, should_execute, rewritten, clarification.\n"
                f"Allowed intents: {INTENTS}.\n"
                "Agents: browser_agent, gmail_agent, system_agent, file_agent, document_agent, chat.\n"
                "Rules:\n"
                "- If it's general knowledge or chit-chat: intent=chat_conversation, should_execute=false.\n"
                "- If unclear: should_execute=false and set clarification.\n"
                "- Do NOT suggest running arbitrary shell commands.\n\n"
                f"Recent messages: {json.dumps(history, ensure_ascii=False)}\n\n"
                f"User: {text}\n"
            ),
        }

        reply = await self.provider.generate_response([prompt])
        data = json.loads(reply)

        intent = str(data.get("intent") or "chat_conversation")
        if intent not in INTENTS:
            intent = "chat_conversation"
        agent = str(data.get("agent") or "chat")
        confidence = float(data.get("confidence") or 0.5)
        should_execute = bool(data.get("should_execute"))
        rewritten = data.get("rewritten")
        clarification = data.get("clarification")

        if confidence < 0.0:
            confidence = 0.0
        if confidence > 1.0:
            confidence = 1.0

        # Guard: if model says execute but doesn't provide a rewritten plan, downgrade.
        if should_execute and (not rewritten or not str(rewritten).strip()):
            should_execute = False
            clarification = clarification or "What would you like me to do exactly?"
            confidence = min(confidence, 0.55)

        res = ReasoningResult(
            intent=intent,
            agent=agent,
            confidence=confidence,
            should_execute=should_execute,
            rewritten=(str(rewritten).strip() if rewritten else None),
            clarification=(str(clarification).strip() if clarification else None),
        )
        try:
            self._llm_cache.set(cache_key, res)
        except Exception:
            pass
        return res
