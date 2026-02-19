from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseAIProvider(ABC):
    """
    Abstract base class for all AI providers.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> str:
        """
        Generate AI response from conversation messages.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if provider is reachable.
        """
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """
        List available models.
        """
        pass
