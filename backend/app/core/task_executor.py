from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.security.confirmation_service import confirmation_service
from app.security.security_logs import log_security_event
from app.security.security_manager import PermissionLevel, security_manager
from app.learning.behavior_tracker import BehaviorTracker
from app.learning.suggestion_engine import SuggestionEngine


PublishFn = Callable[[str, Dict[str, Any]], Awaitable[None]]
DispatchFn = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
ApplyContextFn = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
UpdateContextFn = Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], None]


@dataclass(frozen=True)
class ExecutionSummary:
    status: str  # success | partial | error | needs_confirmation
    tasks: List[Dict[str, Any]]
    completed: List[str]
    failed: Optional[str] = None
    prompt: Optional[str] = None
    confirm_task: Optional[Dict[str, Any]] = None


class TaskExecutor:
    """
    Executes planned tasks sequentially with:
    - dependency/context resolution (via callbacks)
    - security validation
    - progress events
    - early-stop on failure
    """

    def __init__(
        self,
        *,
        user_id: str,
        is_authenticated: bool,
        publish: PublishFn,
        dispatch: DispatchFn,
        apply_chain_context: ApplyContextFn,
        update_chain_context: UpdateContextFn,
        memory_manager: Any | None = None,
    ):
        self.user_id = (user_id or "").strip() or "default"
        self.is_authenticated = bool(is_authenticated)
        self.publish = publish
        self.dispatch = dispatch
        self.apply_chain_context = apply_chain_context
        self.update_chain_context = update_chain_context
        self.memory_manager = memory_manager

    async def execute_tasks(self, tasks: List[Dict[str, Any]]) -> ExecutionSummary:
        chain_context: Dict[str, Any] = {}
        tasks_out: List[Dict[str, Any]] = []
        completed: List[str] = []

        tracker = None
        suggester = None
        try:
            if self.memory_manager and hasattr(self.memory_manager, "db"):
                tracker = BehaviorTracker(self.memory_manager.db, self.user_id)
                suggester = SuggestionEngine(self.memory_manager.db, self.user_id)
        except Exception:
            tracker = None
            suggester = None

        for raw in list(tasks or []):
            resolved = self.apply_chain_context(raw, chain_context)
            params = resolved.get("params") or {}

            decision = security_manager.validate_task(
                resolved,
                user_id=self.user_id,
                is_authenticated=self.is_authenticated,
                confirmed=bool(params.get("_confirmed")),
            )

            if decision.requires_confirmation and decision.prompt:
                confirmation_service.set_pending(self.user_id, resolved, prompt=decision.prompt)
                log_security_event(
                    "security.confirmation_required",
                    {"user_id": self.user_id, "action": resolved.get("action"), "level": decision.level},
                )
                return ExecutionSummary(
                    status="needs_confirmation",
                    tasks=tasks_out,
                    completed=completed,
                    failed=None,
                    prompt=decision.prompt,
                    confirm_task=resolved,
                )

            if not decision.allowed:
                log_security_event(
                    "security.blocked_task",
                    {"user_id": self.user_id, "action": resolved.get("action"), "level": decision.level, "reason": decision.reason},
                )
                blocked = {
                    "status": "error",
                    "agent": "security_manager",
                    "action": resolved.get("action"),
                    "task": resolved.get("text", ""),
                    "result": None,
                    "error": decision.reason or "Blocked for security reasons.",
                }
                tasks_out.append(blocked)
                return ExecutionSummary(
                    status="partial" if completed else "error",
                    tasks=tasks_out,
                    completed=completed,
                    failed=(resolved.get("text") or resolved.get("action") or "task"),
                )

            await self._publish_safe(
                "task_started",
                {"user_id": self.user_id, "task": resolved.get("text", ""), "action": resolved.get("action"), "agent": resolved.get("agent")},
            )

            started = time.perf_counter()
            result = await self.dispatch(resolved)
            duration_s = max(0.0, time.perf_counter() - started)
            tasks_out.append(result)

            # Best-effort task duration metric.
            try:
                from app.monitoring.performance_metrics import performance_metrics

                performance_metrics.observe_task((resolved.get("action") or "").strip(), duration_s)
            except Exception:
                pass

            ok = result.get("status") == "success"
            if ok:
                completed.append((resolved.get("action") or "").strip() or (resolved.get("text") or "task"))
                # Lightweight usage stats + learning behavior updates (best-effort).
                try:
                    action = (resolved.get("action") or "").strip()
                    params = resolved.get("params") or {}
                    if action == "open_application":
                        app = (params.get("app") or "").strip().lower()
                        if app:
                            from app.core.usage_stats import usage_stats
                            usage_stats.bump("app_open", app)
                            if tracker:
                                row = tracker.record(f"open_app:{app}", context={"app": app})
                                if row and suggester:
                                    await suggester.maybe_emit(row)
                    if action == "browser_search":
                        q = (params.get("query") or "").strip()
                        if q and tracker:
                            row = tracker.record(f"web_search:{q.lower()}", context={"query": q})
                            if row and suggester:
                                await suggester.maybe_emit(row)
                    if action == "open_folder":
                        p = (params.get("path") or "").strip()
                        if p and tracker:
                            tracker.record("open_folder", context={"path": p})
                except Exception:
                    pass

            event_type = "task_completed" if ok else "task_failed"
            await self._publish_safe(
                event_type,
                {
                    "user_id": self.user_id,
                    "task": resolved.get("text", ""),
                    "action": resolved.get("action"),
                    "agent": resolved.get("agent"),
                    "status": result.get("status"),
                    "error": result.get("error"),
                },
            )
            # Backwards compatibility for older UIs
            if not ok:
                await self._publish_safe(
                    "task_error",
                    {
                        "user_id": self.user_id,
                        "task": resolved.get("text", ""),
                        "action": resolved.get("action"),
                        "agent": resolved.get("agent"),
                        "status": result.get("status"),
                        "error": result.get("error"),
                    },
                )

            if ok:
                try:
                    if self.memory_manager and decision.level == PermissionLevel.SAFE:
                        self.memory_manager.add_memory(
                            content=f"task_completed action={resolved.get('action')} text={(resolved.get('text') or '').strip()[:140]}",
                            category="task",
                        )
                except Exception:
                    pass

            if not ok:
                return ExecutionSummary(
                    status="partial" if completed else "error",
                    tasks=tasks_out,
                    completed=completed,
                    failed=(resolved.get("text") or resolved.get("action") or "task"),
                )

            self.update_chain_context(resolved, result, chain_context)

        return ExecutionSummary(status="success", tasks=tasks_out, completed=completed)

    async def _publish_safe(self, event_type: str, data: Dict[str, Any]) -> None:
        try:
            await self.publish(event_type, data)
        except Exception:
            return
