"""LLM abstraction layer — provider-agnostic AI client.

Supports: Gemini (google-genai), OpenAI, Anthropic, Ollama (local).
Configure via LLM_PROVIDER and LLM_MODEL in settings/env.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from argplant.shared.config import settings

logger = logging.getLogger("argplant.llm")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    """Provider-agnostic LLM interface."""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        """Send a prompt and return the text response."""

    @abstractmethod
    async def generate_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        """Send a prompt expecting a JSON response."""


# ---------------------------------------------------------------------------
# Gemini implementation
# ---------------------------------------------------------------------------


class GeminiClient(LLMClient):
    """Google Gemini via the google-genai SDK."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        try:
            from google import genai  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "google-genai is required for Gemini. Install with: pip install google-genai"
            ) from None

        self._model_name = model or settings.LLM_MODEL
        self._client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)

    async def generate(self, prompt: str, system: str | None = None) -> str:
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": system}]})
            contents.append({"role": "model", "parts": [{"text": "Entendido."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=contents,
        )
        return response.text or ""

    async def generate_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        full_prompt = f"{prompt}\n\nRespond ONLY with valid JSON. No markdown, no explanation."
        text = await self.generate(full_prompt, system)
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_llm_client() -> LLMClient:
    """Return the configured LLM client based on LLM_PROVIDER setting."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "gemini":
        return GeminiClient()

    # TODO: Add OpenAI, Anthropic, Ollama providers
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}. Supported: gemini")
