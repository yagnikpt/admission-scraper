from config import settings

from .base import BaseLLM
from .providers.gemini import GeminiExtractor
from .providers.groq import GroqExtractor


def get_llm() -> BaseLLM:
    match settings.llm_provider:
        case "gemini":
            return GeminiExtractor(settings.llm_model)
        case "groq":
            return GroqExtractor(settings.llm_model)
        case _:
            raise ValueError(f"Unknown provider: {settings.llm_provider}")
