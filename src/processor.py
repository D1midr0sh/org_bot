from typing import Dict, List, Tuple
import re

from .config import settings
from .llm.base import LLMProvider


def build_prompt_suffix(style: str) -> str:
    style = style or settings.style_mode
    return f"Стиль: {style}."


def apply_custom_dictionary(text: str, style: str | None = None) -> Tuple[str, List[Tuple[str, str]]]:
    """Dictionary pass disabled by design. Return original text, no changes."""
    return text, []


class TextProcessor:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def process(self, text: str, style: str = None, max_alternatives: int = None):
        # Enforce strict mode globally if configured
        if settings.always_strict:
            style = 'strict'
        else:
            style = style or settings.style_mode
        max_alternatives = max_alternatives or settings.max_alternatives

        # No pre/post dictionary passes, delegate fully to LLM
        best, alternatives, explanation = self.provider.replace_anglicisms(
            text, style=style, max_alternatives=max_alternatives
        )

        # Update statistics: naive count of probable replacements
    # Statistics disabled in simplified version

        return {
            "best": best,
            "alternatives": alternatives,
            "explanation": explanation,
            "local_changes": [],
        }
