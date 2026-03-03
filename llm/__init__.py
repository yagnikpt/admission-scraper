from config import settings

from .base import BaseLLM
from .providers.gemini import GeminiExtractor
from .providers.groq import GroqExtractor


def get_llm() -> BaseLLM:
    match settings.llm_provider:
        case "gemini":
            return GeminiExtractor()
        case "groq":
            return GroqExtractor()
        case _:
            raise ValueError(f"Unknown provider: {settings.llm_provider}")
