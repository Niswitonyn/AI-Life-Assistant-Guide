import asyncio
from typing import Any, Dict

from app.agents.base_agent import BaseAgent
from app.core.system_logs import log_system_event
from app.services.file_system_service import FileSystemError, FileSystemService


class FileAgent(BaseAgent):
    name = "file_agent"
    description = "Safe file system agent (find/open/create/delete/list) within allowed directories."

    def __init__(self):
        self.fs = FileSystemService()

    async def execute(self, task: dict):
        task = task or {}
        action = (task.get("action") or "").strip()
        params = task.get("params") or {}
        task_text = task.get("text", "")

        try:
            if action in {"find_file", "file_find"}:
                name = (params.get("name") or params.get("filename") or "").strip()
                res = await asyncio.to_thread(self.fs.search_file, name, max_results=int(params.get("max_results", 10)))
                log_system_event("find_file", {"name": name, "ok": res.ok})
                return self._wrap(res, task_text, "find_file")

            if action == "open_file":
                value = (params.get("path") or params.get("name") or params.get("filename") or "").strip()
                res = await asyncio.to_thread(self.fs.open_file, value)
                log_system_event("open_file", {"value": value, "ok": res.ok})
                return self._wrap(res, task_text, "open_file")

            if action in {"create_folder", "folder_create"}:
                name = (params.get("name") or params.get("folder_name") or "").strip()
                loc = (params.get("location") or params.get("base") or "documents").strip()
                res = await asyncio.to_thread(self.fs.create_folder, name, loc)
                log_system_event("create_folder", {"name": name, "location": loc, "ok": res.ok})
                return self._wrap(res, task_text, "create_folder")

            if action == "delete_file":
                value = (params.get("path") or params.get("name") or params.get("filename") or "").strip()
                res = await asyncio.to_thread(self.fs.delete_file, value)
                log_system_event("delete_file", {"value": value, "ok": res.ok})
                return self._wrap(res, task_text, "delete_file")

            if action in {"list_files", "list_directory"}:
                path = (params.get("path") or params.get("location") or "").strip()
                res = await asyncio.to_thread(self.fs.list_directory, path, limit=int(params.get("limit", 50)))
                log_system_event("list_files", {"path": path, "ok": res.ok})
                return self._wrap(res, task_text, "list_files")

            return self._err(task_text, action, f"Unsupported action: {action}")
        except FileSystemError as e:
            log_system_event(action or "file_error", {"task": task_text}, error=str(e))
            return self._err(task_text, action, str(e))
        except Exception as e:
            log_system_event(action or "file_error", {"task": task_text}, error=str(e))
            return self._err(task_text, action, str(e) or "File action failed")

    def _wrap(self, res, task_text: str, action: str):
        data = res.data if isinstance(res.data, dict) else {}
        data.setdefault("message", res.message)
        return {
            "status": "success" if res.ok else "error",
            "agent": self.name,
            "action": action,
            "task": task_text,
            "data": data if res.ok else data,
            "result": data if res.ok else None,
            "error": None if res.ok else res.message,
        }

    def _err(self, task_text: str, action: str, error: str):
        return {"status": "error", "agent": self.name, "action": action, "task": task_text, "data": None, "result": None, "error": error}
