from __future__ import annotations

from typing import Any, Dict, Optional

from app.agents.gmail_agent import GmailAgent
from app.ai.base_provider import BaseAIProvider


class EmailService:
    """
    Thin service wrapper for email operations used by controllers/routers.
    """

    def __init__(self, user_id: str, *, provider: Optional[BaseAIProvider] = None):
        self.user_id = user_id
        self.provider = provider

    def agent(self) -> GmailAgent:
        return GmailAgent(user_id=self.user_id, provider=self.provider)

    async def read_inbox(self, limit: int = 5) -> Dict[str, Any]:
        return await self.agent().execute({"action": "read_inbox", "params": {"limit": limit}, "text": "read inbox"})

    async def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        return await self.agent().execute({"action": "search_email", "params": {"query": query, "limit": limit}, "text": f"search {query}"})

