from typing import List, Dict
import google.generativeai as genai

from app.ai.base_provider import BaseAIProvider
from app.security.key_manager import key_manager


class GeminiProvider(BaseAIProvider):
    """
    AI Provider for Google Gemini models.
    """

    def __init__(self, model: str = "gemini-1.5-flash"):
        super().__init__()
        self.model_name = model

        api_key = key_manager.get_key("gemini")

        if not api_key:
            raise ValueError("Gemini API key not configured")

        genai.configure(api_key=api_key)

        self.client = genai.GenerativeModel(self.model_name)

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> str:

        # Convert messages → simple prompt
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            prompt += f"{role}: {content}\n"

        response = self.client.generate_content(prompt)

        return response.text if response.text else ""

    async def health_check(self) -> bool:
        try:
            _ = self.client.generate_content("hello")
            return True
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        return [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]
