from app.agents.base_agent import BaseAgent


class ChromeAgent(BaseAgent):
    """
    Compatibility wrapper.

    Prefer using `BrowserAgent` + `BrowserAutomation` for all browser control.
    """

    name = "chrome_agent"
    description = "Deprecated. Use browser_agent with Playwright automation."

    async def execute(self, task: dict):
        from app.agents.browser_agent import BrowserAgent

        action = (task or {}).get("action") or ""
        params = (task or {}).get("params") or {}

        if action in {"open", "chrome_open"}:
            return await BrowserAgent().execute({"text": task.get("text", ""), "action": "browser_open", "params": {}})

        if action in {"search", "chrome_search"}:
            return await BrowserAgent().execute({"text": task.get("text", ""), "action": "browser_search", "params": {"query": params.get("query", ""), "limit": 5}})

        if action in {"images", "chrome_images"}:
            return await BrowserAgent().execute({"text": task.get("text", ""), "action": "browser_download_images", "params": {"query": params.get("query", ""), "limit": 10}})

        return {"status": "error", "agent": self.name, "action": action, "task": task.get("text", ""), "data": None, "error": f"Unsupported action: {action}"}
