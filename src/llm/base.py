from abc import ABC, abstractmethod
from typing import List, Tuple


class LLMProvider(ABC):
    @abstractmethod
    def replace_anglicisms(self, text: str, style: str = 'auto', max_alternatives: int = 3) -> Tuple[str, List[str], str]:
        """
        Analyze text and replace borrowings with native Russian alternatives.
        Returns: (best_variant, alternatives, explanation)
        """
        raise NotImplementedError
