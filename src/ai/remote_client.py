import logging
from typing import List

import requests

from config.settings import LLMConfig
from .base import LLMClient
from .prompts import build_quiz_prompt


class RemoteLLMClient(LLMClient):
    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    def choose_answer(self, question: str, options: List[str]) -> str:
        prompt = build_quiz_prompt(question, options)

        payload = {
            "model": self._config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a reading comprehension assistant. "
                        "Choose the single best answer option and respond with the option "
                        "letter and the full option text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self._config.base_url}/chat/completions".rstrip("/")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        try:
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError) as exc:
            logging.error("Unexpected LLM response format: %s", data)
            raise RuntimeError("LLM response format error") from exc

        return content
