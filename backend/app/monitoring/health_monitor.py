from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text

from app.database.db import engine
from app.database.init_db import init_db
from app.monitoring.alert_manager import alert_manager
from app.monitoring.monitor_logs import log_monitor_event
from app.monitoring.performance_metrics import performance_metrics
from app.monitoring.status_registry import status_registry
from app.rag.vector_store import vector_store
from app.services.event_bus import get_event_bus


def _ts() -> float:
    return time.time()


class HealthMonitor:
    def __init__(self, *, interval_s: float = 30.0) -> None:
        self.interval_s = float(interval_s)
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._retry_count: Dict[str, int] = {}
        self._next_retry_at: Dict[str, float] = {}
        self._last_component_state: Dict[str, str] = {}

    @property
    def is_running(self) -> bool:
        return bool(self._task and not self._task.done())

    async def start(self) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="health_monitor")
        log_monitor_event("monitor.started", {"interval_s": self.interval_s})

    async def stop(self) -> None:
        self._stop.set()
        if not self._task:
            return
        try:
            self._task.cancel()
        except Exception:
            pass
        try:
            await asyncio.wait_for(self._task, timeout=3.0)
        except Exception:
            pass
        log_monitor_event("monitor.stopped", {})

    async def restart_component(self, component: str) -> Dict[str, Any]:
        comp = (component or "").strip().lower()
        if comp in ("db", "database"):
            ok, err = await self._recover_database(force=True)
            return {"status": "success" if ok else "error", "component": "database", "error": err}
        if comp in ("rag", "rag_vector_store", "vector_store"):
            ok, err = await self._recover_vector_store(force=True)
            return {"status": "success" if ok else "error", "component": "rag_vector_store", "error": err}
        if comp in ("tts", "voice_tts", "text_to_speech"):
            ok, err = await self._recover_tts(force=True)
            return {"status": "success" if ok else "error", "component": "voice_tts", "error": err}
        return {"status": "error", "component": comp, "error": "Unsupported component"}

    async def _run(self) -> None:
        bus = get_event_bus()
        while not self._stop.is_set():
            checked_at = _ts()
            throttled = False
            try:
                performance_metrics.update_system_metrics()
                throttled = performance_metrics.is_high_load()
                components = await self._check_components(throttled=throttled)
                snapshot = self._build_snapshot(components, checked_at=checked_at, throttled=throttled)
                status_registry.set_snapshot(snapshot)
                try:
                    await bus.publish("health.update", snapshot)
                except Exception:
                    pass
                log_monitor_event("health.update", {"status": snapshot.get("status"), "throttled": throttled})
            except Exception as exc:
                # Keep loop alive.
                err = str(exc)
                snapshot = {
                    "status": "unhealthy",
                    "checked_at": checked_at,
                    "components": {"health_monitor": {"status": "failed", "error": err}},
                    "metrics": performance_metrics.snapshot(),
                    "throttled": throttled,
                }
                status_registry.set_snapshot(snapshot)
                try:
                    await bus.publish("health.update", snapshot)
                except Exception:
                    pass
                try:
                    await alert_manager.emit(level="critical", component="health_monitor", message="Health monitor failed", data={"error": err})
                except Exception:
                    pass

            sleep_s = self.interval_s * (2.0 if throttled else 1.0)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=max(2.0, sleep_s))
            except asyncio.TimeoutError:
                continue

    def _build_snapshot(self, components: Dict[str, Dict[str, Any]], *, checked_at: float, throttled: bool) -> Dict[str, Any]:
        # Determine overall status.
        critical = {"database", "rag_vector_store"}
        unhealthy = []
        degraded = []
        for name, st in (components or {}).items():
            s = (st.get("status") or "").lower()
            if s in ("failed", "error", "unhealthy", "blocked"):
                if name in critical:
                    unhealthy.append(name)
                else:
                    degraded.append(name)

        overall = "healthy"
        if unhealthy:
            overall = "unhealthy"
        elif degraded:
            overall = "degraded"

        return {
            "status": overall,
            "checked_at": checked_at,
            "components": components,
            "metrics": performance_metrics.snapshot(),
            "throttled": throttled,
        }

    async def _check_components(self, *, throttled: bool) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}

        db_ok, db_err = await self._check_database()
        if not db_ok:
            recovered, rerr = await self._recover_database()
            db_ok = recovered
            db_err = rerr or db_err
        out["database"] = {"status": "connected" if db_ok else "failed", "error": db_err}
        await self._maybe_alert("database", out["database"], critical=True)

        rag_ok, rag_err = await self._check_vector_store()
        if not rag_ok:
            recovered, rerr = await self._recover_vector_store()
            rag_ok = recovered
            rag_err = rerr or rag_err
        out["rag_vector_store"] = {"status": "running" if rag_ok else "failed", "error": rag_err}
        await self._maybe_alert("rag_vector_store", out["rag_vector_store"], critical=True)

        # Voice TTS is optional; treat failures as degraded.
        tts_ok, tts_err = await self._check_tts()
        if not tts_ok:
            recovered, rerr = await self._recover_tts()
            tts_ok = recovered
            tts_err = rerr or tts_err
        out["voice_tts"] = {"status": "running" if tts_ok else "failed", "error": tts_err}
        await self._maybe_alert("voice_tts", out["voice_tts"], critical=False)

        # Import checks (skip some under high load).
        if not throttled:
            out.update(self._check_imports())
        else:
            out["imports"] = {"status": "skipped", "error": "throttled"}

        return out

    async def _maybe_alert(self, component: str, state: Dict[str, Any], *, critical: bool) -> None:
        status = (state.get("status") or "unknown").lower()
        prev = self._last_component_state.get(component)
        self._last_component_state[component] = status

        if prev == status:
            return
        if status in ("failed", "error", "unhealthy"):
            level = "critical" if critical else "warning"
            msg = f"{component} reported {status}"
            data = {"error": state.get("error")}
            await alert_manager.emit(level=level, component=component, message=msg, data=data, min_interval_s=60.0)
        elif prev in ("failed", "error", "unhealthy") and status in ("connected", "running"):
            await alert_manager.emit(level="info", component=component, message=f"{component} recovered", data={}, min_interval_s=30.0)

    def _check_imports(self) -> Dict[str, Dict[str, Any]]:
        checks = {
            "brain_controller": ("app.core.brain_controller", "BrainController"),
            "reasoning_engine": ("app.core.reasoning_engine", "ReasoningEngine"),
            "task_planner": ("app.core.task_planner", "TaskPlanner"),
            "task_executor": ("app.core.task_executor", "TaskExecutor"),
            "browser_agent": ("app.agents.browser_agent", "BrowserAgent"),
            "gmail_agent": ("app.agents.gmail_agent", "GmailAgent"),
            "system_agent": ("app.agents.system_agent", "SystemAgent"),
            "file_agent": ("app.agents.file_agent", "FileAgent"),
            "document_agent": ("app.agents.document_agent", "DocumentAgent"),
        }
        out: Dict[str, Dict[str, Any]] = {}
        for name, (mod, sym) in checks.items():
            try:
                m = __import__(mod, fromlist=[sym])
                _ = getattr(m, sym)
                out[name] = {"status": "running"}
            except Exception as exc:
                out[name] = {"status": "failed", "error": str(exc)}
        return out

    async def _check_database(self) -> Tuple[bool, Optional[str]]:
        try:
            def _check() -> None:
                with engine.begin() as conn:
                    conn.execute(text("SELECT 1"))

            await asyncio.to_thread(_check)
            return True, None
        except Exception as exc:
            return False, str(exc)

    async def _recover_database(self, *, force: bool = False) -> Tuple[bool, Optional[str]]:
        return await self._recover_with_backoff("database", self._do_recover_database, force=force)

    async def _do_recover_database(self) -> Tuple[bool, Optional[str]]:
        try:
            await asyncio.to_thread(init_db)
            ok, err = await self._check_database()
            return ok, err
        except Exception as exc:
            return False, str(exc)

    async def _check_vector_store(self) -> Tuple[bool, Optional[str]]:
        try:
            info = {}
            if hasattr(vector_store, "health"):
                info = vector_store.health()
            else:
                # Legacy: just touch data.
                info = {"count": len(vector_store.all_documents())}
            ok = True
            if isinstance(info, dict) and info.get("ok") is False:
                ok = False
            return ok, None if ok else "vector_store health() reported not ok"
        except Exception as exc:
            return False, str(exc)

    async def _recover_vector_store(self, *, force: bool = False) -> Tuple[bool, Optional[str]]:
        return await self._recover_with_backoff("rag_vector_store", self._do_recover_vector_store, force=force)

    async def _do_recover_vector_store(self) -> Tuple[bool, Optional[str]]:
        try:
            if hasattr(vector_store, "reload"):
                await asyncio.to_thread(vector_store.reload)
            ok, err = await self._check_vector_store()
            return ok, err
        except Exception as exc:
            return False, str(exc)

    async def _check_tts(self) -> Tuple[bool, Optional[str]]:
        try:
            from app.voice import text_to_speech

            if hasattr(text_to_speech, "health"):
                info = text_to_speech.health()
                if isinstance(info, dict) and info.get("ok") is False:
                    return False, info.get("error") or "tts unhealthy"
                return True, None
            return True, None
        except Exception as exc:
            return False, str(exc)

    async def _recover_tts(self, *, force: bool = False) -> Tuple[bool, Optional[str]]:
        return await self._recover_with_backoff("voice_tts", self._do_recover_tts, force=force)

    async def _do_recover_tts(self) -> Tuple[bool, Optional[str]]:
        try:
            from app.voice import text_to_speech

            if hasattr(text_to_speech, "reset_tts"):
                await asyncio.to_thread(text_to_speech.reset_tts)
            ok, err = await self._check_tts()
            return ok, err
        except Exception as exc:
            return False, str(exc)

    async def _recover_with_backoff(
        self,
        key: str,
        fn,
        *,
        force: bool = False,
        max_retries: int = 3,
        base_cooldown_s: float = 30.0,
    ) -> Tuple[bool, Optional[str]]:
        now = _ts()
        if not force:
            if self._retry_count.get(key, 0) >= int(max_retries):
                return False, "max recovery attempts reached"
            next_at = self._next_retry_at.get(key, 0.0)
            if next_at and now < next_at:
                return False, "recovery cooldown active"

        self._retry_count[key] = self._retry_count.get(key, 0) + 1
        cooldown = float(base_cooldown_s) * float(self._retry_count[key])
        self._next_retry_at[key] = now + cooldown

        log_monitor_event("recovery.attempt", {"component": key, "attempt": self._retry_count[key], "cooldown_s": cooldown})
        ok, err = await fn()
        if ok:
            self._retry_count[key] = 0
            self._next_retry_at[key] = 0.0
        else:
            await alert_manager.emit(
                level="warning",
                component=key,
                message=f"Recovery attempt failed for {key}",
                data={"error": err, "attempt": self._retry_count[key]},
                min_interval_s=60.0,
            )
        return ok, err


health_monitor = HealthMonitor(interval_s=30.0)

