"""LiteLLM provider implementation for the AI ecosystem.

Wraps LiteLLM behind the LLMProvider ABC, enabling provider-agnostic
LLM completions. Provider selection is configured via environment variables:
- LITELLM_DEFAULT_MODEL: Default model identifier
- LITELLM_PROVIDERS: Comma-separated list of configured providers

Implements retry with exponential backoff for transient errors (429 rate limits)
but does NOT retry on authentication (401) or invalid request (400) errors.
"""

import os
import time
from typing import Any

try:
    import litellm
    from litellm import RateLimitError, AuthenticationError, BadRequestError

    HAS_LITELLM = True
except ImportError:
    HAS_LITELLM = False
    RateLimitError = Exception  # type: ignore
    AuthenticationError = Exception  # type: ignore
    BadRequestError = Exception  # type: ignore

from src.ai.domain.errors import ContextError
from src.ai.domain.interfaces import LLMProvider
from src.ai.domain.models import LLMRequest, LLMResponse


class LiteLLMProviderImpl(LLMProvider):
    """Concrete LLMProvider implementation using LiteLLM.

    Provider selection is driven by environment variables.
    The `complete()` method handles retry logic for transient errors.
    """

    # Errors that should NOT be retried
    _NON_RETRYABLE = (AuthenticationError, BadRequestError)

    def __init__(
        self,
        model: str | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        """Initialize the LiteLLM provider.

        Args:
            model: Default model identifier. Falls back to LITELLM_DEFAULT_MODEL env var.
            max_retries: Maximum retry attempts for transient errors.
            base_delay: Base delay in seconds for exponential backoff.
        """
        if not HAS_LITELLM:
            raise ContextError(
                "litellm is not installed. Run: pip install litellm>=1.40.0"
            )

        self._model = model or os.getenv("LITELLM_DEFAULT_MODEL", "gpt-4o-mini")
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._provider = "openai"  # default provider prefix

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM completion via LiteLLM.

        Implements retry with exponential backoff for rate limit errors (429).
        Does NOT retry on authentication (401) or bad request (400) errors.

        Args:
            request: LLMRequest with prompt, context, model, and parameters.

        Returns:
            LLMResponse with content, model, usage, and metadata.

        Raises:
            AuthenticationError: On 401 auth failures (not retried).
            BadRequestError: On 400 invalid request errors (not retried).
            ContextError: On exhausted retries or other failures.
        """
        model = request.model or self._model
        messages = self._build_messages(request)

        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            start_time = time.time()
            try:
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                )

                latency_ms = (time.time() - start_time) * 1000

                # Extract usage statistics
                usage = {}
                if hasattr(response, "usage") and response.usage:
                    usage = {
                        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(
                            response.usage, "completion_tokens", 0
                        ),
                        "total_tokens": getattr(response.usage, "total_tokens", 0),
                    }

                # Extract content
                content = ""
                if response.choices and len(response.choices) > 0:
                    content = response.choices[0].message.content or ""

                # Extract cost if available
                cost_usd = getattr(response, "_hidden_params", {}).get(
                    "additional_headers", {}
                ).get("response_cost")

                return LLMResponse(
                    content=content,
                    model=model,
                    usage=usage,
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                    metadata={"attempt": attempt + 1},
                )

            except self._NON_RETRYABLE as e:
                # Auth or bad request — never retry
                raise

            except RateLimitError as e:
                last_error = e
                if attempt < self._max_retries:
                    delay = self._base_delay * (2**attempt)
                    time.sleep(delay)
                continue

            except Exception as e:
                last_error = e
                if attempt < self._max_retries:
                    delay = self._base_delay * (2**attempt)
                    time.sleep(delay)
                continue

        # All retries exhausted
        raise ContextError(
            f"LLM completion failed after {self._max_retries + 1} attempts: {last_error}"
        )

    def set_provider(self, provider: str) -> None:
        """Switch the underlying provider prefix.

        Args:
            provider: Provider identifier (e.g. "openai", "claude", "gemini", "azure").
        """
        self._provider = provider

    def _build_messages(self, request: LLMRequest) -> list[dict[str, str]]:
        """Build the messages list for LiteLLM.

        Args:
            request: The LLM request with prompt and optional context.

        Returns:
            List of message dicts for the completion API.
        """
        messages: list[dict[str, str]] = []

        if request.context:
            messages.append({"role": "system", "content": request.context})

        messages.append({"role": "user", "content": request.prompt})

        return messages
