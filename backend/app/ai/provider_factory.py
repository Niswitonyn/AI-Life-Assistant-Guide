from typing import Optional

from app.config.settings import settings
from app.ai.base_provider import BaseAIProvider
from app.ai.ollama_provider import OllamaProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.gemini_provider import GeminiProvider   # ✅ ADD THIS


class ProviderFactory:
    """
    Factory class to create AI provider instances.
    """

    def __init__(self):
        self.default_provider = settings.DEFAULT_PROVIDER

    def get_provider(
        self,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> BaseAIProvider:

        provider_name = provider_name or self.default_provider

        # ✅ Ollama
        if provider_name.lower() == "ollama":
            return OllamaProvider(model=model or "llama3")

        # ✅ OpenAI
        elif provider_name.lower() == "openai":
            return OpenAIProvider(model=model or "gpt-4o-mini")

        # ✅ Gemini
        elif provider_name.lower() == "gemini":
            return GeminiProvider(model=model or "gemini-1.5-flash")

        raise ValueError(f"Unsupported provider: {provider_name}")


# Singleton
provider_factory = ProviderFactory()
