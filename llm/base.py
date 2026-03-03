from abc import ABC, abstractmethod
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseLLM(ABC, Generic[T]):
    """Abstract base class for LLM providers."""

    response_model: ClassVar[type]

    @abstractmethod
    def extract_announcements(self, content: str, url: str) -> T:
        """Extracts announcements from the given content and URL using LLM."""
        pass
