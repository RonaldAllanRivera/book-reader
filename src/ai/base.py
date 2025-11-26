from abc import ABC, abstractmethod
from typing import List


class LLMClient(ABC):
    @abstractmethod
    def choose_answer(self, question: str, options: List[str]) -> str:
        """Return the model's suggested answer for the given question/options."""
        raise NotImplementedError
