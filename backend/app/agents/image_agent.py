from app.agents.base_agent import BaseAgent


class ImageAgent(BaseAgent):
    """
    Compatibility wrapper.

    Prefer using `BrowserAgent` + `BrowserAutomation` for image downloads.
    """

    name = "image_agent"
    description = "Deprecated. Use browser_agent for Playwright-based image downloads."

    async def execute(self, task: dict):
        from app.agents.browser_agent import BrowserAgent

        params = (task or {}).get("params") or {}
        topic = (params.get("topic") or params.get("query") or "").strip()
        limit = int(params.get("limit", 10))

        return await BrowserAgent().execute(
            {
                "text": task.get("text", ""),
                "action": "browser_download_images",
                "params": {"query": topic, "limit": limit},
            }
        )
