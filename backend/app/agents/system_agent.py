from __future__ import annotations

import asyncio
from typing import Any, Dict

from app.agents.base_agent import BaseAgent
from app.core.system_logs import log_system_event
from app.services.system_control import SystemControl, SystemControlError


class SystemAgent(BaseAgent):
    name = "system_agent"
    description = "Windows PC control agent (apps/volume/shutdown/lock/folders) with safeguards."

    def __init__(self):
        self.control = SystemControl()

    async def execute(self, task: Dict[str, Any]):
        task = task or {}
        action = (task.get("action") or "").strip()
        params = task.get("params") or {}
        task_text = task.get("text", "")

        try:
            if action == "open_application":
                app = (params.get("app") or params.get("application") or "").strip()
                res = await asyncio.to_thread(self.control.open_application, app)
                log_system_event("open_application", {"app": app, "ok": res.ok})
                return self._wrap(res, task_text, action)

            if action == "shutdown":
                res = await asyncio.to_thread(self.control.shutdown_pc)
                log_system_event("shutdown", {"ok": res.ok})
                return self._wrap(res, task_text, action)

            if action == "restart":
                res = await asyncio.to_thread(self.control.restart_pc)
                log_system_event("restart", {"ok": res.ok})
                return self._wrap(res, task_text, action)

            if action == "lock_screen":
                res = await asyncio.to_thread(self.control.lock_screen)
                log_system_event("lock_screen", {"ok": res.ok})
                return self._wrap(res, task_text, action)

            if action == "volume_control":
                mode = (params.get("mode") or "").strip().lower()
                steps = int(params.get("steps", 6))
                if mode in {"up", "increase"}:
                    res = await asyncio.to_thread(self.control.increase_volume, steps)
                elif mode in {"down", "decrease"}:
                    res = await asyncio.to_thread(self.control.decrease_volume, steps)
                elif mode == "mute":
                    res = await asyncio.to_thread(self.control.mute_volume)
                elif mode == "unmute":
                    res = await asyncio.to_thread(self.control.unmute_volume)
                elif mode in {"set", "set_volume"}:
                    level = params.get("level", params.get("volume", params.get("value", None)))
                    if level is None or str(level).strip() == "":
                        return self._err(task_text, action, "Missing volume level (0-100).")
                    res = await asyncio.to_thread(self.control.set_volume, int(level))
                else:
                    return self._err(task_text, action, f"Unsupported volume mode: {mode}")
                log_system_event(
                    "volume_control",
                    {"mode": mode, "steps": steps, "level": params.get("level"), "ok": res.ok},
                )
                return self._wrap(res, task_text, action)

            if action == "open_folder":
                path = (params.get("path") or "").strip()
                res = await asyncio.to_thread(self.control.open_folder, path)
                log_system_event("open_folder", {"path": path, "ok": res.ok})
                return self._wrap(res, task_text, action)

            return self._err(task_text, action, f"Unsupported action: {action}")
        except SystemControlError as e:
            log_system_event(action or "system_error", {"task": task_text}, error=str(e))
            return self._err(task_text, action, str(e))
        except Exception as e:
            log_system_event(action or "system_error", {"task": task_text}, error=str(e))
            return self._err(task_text, action, str(e) or "System action failed")

    def _wrap(self, res, task_text: str, action: str):
        data = res.data if isinstance(res.data, dict) else {}
        data.setdefault("message", res.message)
        return {
            "status": "success" if res.ok else "error",
            "agent": self.name,
            "action": action,
            "task": task_text,
            "data": data if res.ok else None,
            "result": data if res.ok else None,
            "error": None if res.ok else res.message,
        }

    def _err(self, task_text: str, action: str, error: str):
        return {
            "status": "error",
            "agent": self.name,
            "action": action,
            "task": task_text,
            "data": None,
            "result": None,
            "error": error,
        }
