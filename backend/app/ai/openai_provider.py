from typing import List, Dict
from openai import AsyncOpenAI

from app.ai.base_provider import BaseAIProvider
from app.security.key_manager import key_manager


class OpenAIProvider(BaseAIProvider):
    """
    AI Provider for OpenAI models.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        super().__init__()
        self.model = model

        # Load encrypted API key
        api_key = key_manager.get_key("openai")

        if not api_key:
            raise ValueError("OpenAI API key not configured")

        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> str:

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        return response.choices[0].message.content

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        models = await self.client.models.list()
        return [m.id for m in models.data]
