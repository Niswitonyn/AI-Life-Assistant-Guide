from typing import List, Dict
import httpx

from app.ai.base_provider import BaseAIProvider
from app.config.settings import settings


class OllamaProvider(BaseAIProvider):
    """
    AI Provider for local Ollama models.
    """

    def __init__(self, model: str = "llama3"):
        super().__init__()
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = model

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> str:

        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        data = response.json()

        return data["message"]["content"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

        data = response.json()

        models = [m["name"] for m in data.get("models", [])]

        return models

