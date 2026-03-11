from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, task: Dict[str, Any]):
        """
        Execute a task and return a structured JSON-serializable dict.
        """
        raise NotImplementedError

