from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from app.agents.base_agent import BaseAgent
from app.core.browser_logs import browser_log
from app.services.browser_automation import BrowserAutomationError, get_browser_automation


class BrowserAgent(BaseAgent):
    name = "browser_agent"
    description = "Unified browser automation agent (open/search/visit/extract/download) via Playwright."

    async def execute(self, task: Dict[str, Any]):
        task = task or {}
        action = (task.get("action") or "").strip()
        params = task.get("params") or {}
        task_text = task.get("text", "")

        automation = await get_browser_automation()

        try:
            if action in {"browser_open", "open_browser", "open_chrome"}:
                async with browser_log(command="browser_open", task=task_text):
                    await automation.open_browser()
                return self._ok(task_text, "browser_open", {"opened": True})

            if action in {"browser_visit", "visit_url", "open_website"}:
                url = (params.get("url") or "").strip()
                async with browser_log(command="browser_visit", task=task_text):
                    data = await automation.visit_url(url)
                return self._ok(task_text, "browser_visit", data)

            if action in {"browser_search", "search"}:
                query = (params.get("query") or "").strip()
                limit = int(params.get("limit", 5))
                async with browser_log(command="browser_search", task=task_text):
                    data = await automation.search_google(query, limit=limit)
                return self._ok(task_text, "browser_search", data)

            if action in {"browser_extract", "extract"}:
                async with browser_log(command="browser_extract", task=task_text):
                    titles, paragraphs, links = await asyncio.gather(
                        automation.extract_titles(limit=int(params.get("title_limit", 50))),
                        automation.extract_paragraphs(limit=int(params.get("paragraph_limit", 80))),
                        automation.extract_links(limit=int(params.get("link_limit", 100))),
                    )
                return self._ok(
                    task_text,
                    "browser_extract",
                    {"titles": titles, "paragraphs": paragraphs, "links": links},
                )

            if action in {"browser_collect_info", "collect_information"}:
                topic = (params.get("topic") or params.get("query") or "").strip()
                limit = int(params.get("limit", 5))
                async with browser_log(command="browser_collect_info", task=task_text):
                    search_data = await automation.search_google(topic, limit=limit)
                    results = (search_data.get("results") or []) if isinstance(search_data, dict) else []
                    first_link = (results[0].get("link") if results else "") or ""
                    if first_link:
                        await automation.open_url(first_link)
                        titles = await automation.extract_titles(limit=20)
                        paragraphs = await automation.extract_paragraphs(limit=30)
                        links = await automation.extract_links(limit=30)
                        page = {"url": first_link, "titles": titles, "paragraphs": paragraphs, "links": links}
                    else:
                        page = None
                return self._ok(
                    task_text,
                    "browser_collect_info",
                    {
                        "source": "google",
                        "query": topic,
                        "results": results,
                        "page": page,
                    },
                )

            if action in {"browser_download_images", "download_images"}:
                query = (params.get("query") or params.get("topic") or "").strip()
                limit = int(params.get("limit", 10))
                async with browser_log(command="browser_download_images", task=task_text) as log:
                    data = await automation.download_images(query, limit=limit)
                downloaded = int(data.get("downloaded", 0)) if isinstance(data, dict) else 0
                log.add_download_count(downloaded)
                return self._ok(task_text, "browser_download_images", data)

            if action in {"browser_screenshot", "screenshot"}:
                label = (params.get("label") or "page").strip()
                async with browser_log(command="browser_screenshot", task=task_text):
                    path = await automation.take_screenshot(label=label)
                return self._ok(task_text, "browser_screenshot", {"path": path})

            if action in {"browser_close", "close_browser"}:
                async with browser_log(command="browser_close", task=task_text):
                    await automation.close_browser()
                return self._ok(task_text, "browser_close", {"closed": True})

            return self._err(task_text, action, f"Unsupported action: {action}")
        except BrowserAutomationError as e:
            return self._err(task_text, action, str(e))
        except Exception as e:
            return self._err(task_text, action, str(e) or "Browser task failed")

    def _ok(self, task_text: str, action: str, data: Dict[str, Any]):
        return {
            "status": "success",
            "agent": self.name,
            "action": action,
            "task": task_text,
            "data": data,
            "result": data,  # Back-compat for existing BrainController formatting.
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
