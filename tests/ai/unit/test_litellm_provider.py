"""Unit tests for LiteLLM provider (mocked).

Tests:
- Provider initialization and model selection
- Successful completion with mocked LiteLLM
- Rate limit retry (429) with exponential backoff
- Auth error (401) is NOT retried
- Provider switching
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.domain.errors import ContextError
from src.ai.domain.models import LLMRequest
from src.ai.infrastructure.llm.litellm_provider import LiteLLMProviderImpl


@pytest.fixture
def provider():
    """Create a LiteLLM provider with mocked litellm."""
    import litellm
    with patch("src.ai.infrastructure.llm.litellm_provider.HAS_LITELLM", True):
        with patch.object(litellm, "completion") as mock_completion:
            mock_completion.return_value = MagicMock()
            return LiteLLMProviderImpl(model="gpt-4o-mini", max_retries=2)


class TestLiteLLMProviderInit:
    """Test provider initialization."""

    def test_init_with_default_model(self):
        """Provider uses default model when none specified."""
        import litellm
        with patch("src.ai.infrastructure.llm.litellm_provider.HAS_LITELLM", True):
            with patch.object(litellm, "completion"):
                p = LiteLLMProviderImpl()
                assert p._model == "gpt-4o-mini"

    def test_init_with_custom_model(self):
        """Provider uses custom model when specified."""
        import litellm
        with patch("src.ai.infrastructure.llm.litellm_provider.HAS_LITELLM", True):
            with patch.object(litellm, "completion"):
                p = LiteLLMProviderImpl(model="claude-3-sonnet")
                assert p._model == "claude-3-sonnet"

    def test_init_without_litellm_raises(self):
        """Provider raises ContextError when litellm is not installed."""
        with patch("src.ai.infrastructure.llm.litellm_provider.HAS_LITELLM", False):
            with pytest.raises(ContextError, match="litellm is not installed"):
                LiteLLMProviderImpl()


class TestLiteLLMProviderComplete:
    """Test LLM completion (mocked)."""

    def test_successful_completion(self, provider):
        """Provider returns LLMResponse on successful completion."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello, world!"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_response._hidden_params = {}

        with patch(
            "src.ai.infrastructure.llm.litellm_provider.litellm.completion",
            return_value=mock_response,
        ):
            request = LLMRequest(prompt="Say hello")
            result = provider.complete(request)

            assert result.content == "Hello, world!"
            assert result.usage["prompt_tokens"] == 10
            assert result.usage["completion_tokens"] == 20
            assert result.usage["total_tokens"] == 30
            assert result.model == "gpt-4o-mini"

    def test_completion_with_context(self, provider):
        """Provider includes context as system message."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response with context"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10
        mock_response.usage.total_tokens = 15
        mock_response._hidden_params = {}

        with patch(
            "src.ai.infrastructure.llm.litellm_provider.litellm.completion",
            return_value=mock_response,
        ) as mock_completion:
            request = LLMRequest(
                prompt="Analyze this",
                context="You are a helpful assistant",
            )
            provider.complete(request)

            # Verify messages include system context
            call_args = mock_completion.call_args
            messages = call_args.kwargs.get("messages", call_args[1].get("messages"))
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are a helpful assistant"
            assert messages[1]["role"] == "user"

    def test_completion_uses_request_model(self, provider):
        """Provider uses model from request if specified."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_response.usage.total_tokens = 2
        mock_response._hidden_params = {}

        with patch(
            "src.ai.infrastructure.llm.litellm_provider.litellm.completion",
            return_value=mock_response,
        ) as mock_completion:
            request = LLMRequest(prompt="test", model="claude-3-opus")
            provider.complete(request)

            call_args = mock_completion.call_args
            model = call_args.kwargs.get("model", call_args[1].get("model"))
            assert model == "claude-3-opus"


class TestLiteLLMProviderRetry:
    """Test retry behavior."""

    def test_rate_limit_retry_succeeds(self, provider):
        """Provider retries on 429 and succeeds on second attempt."""
        import httpx
        from litellm import RateLimitError

        rate_limit_err = RateLimitError(
            message="rate limit",
            llm_provider="openai",
            model="gpt-4o-mini",
            response=httpx.Response(status_code=429, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")),
        )

        # First call fails with rate limit, second succeeds
        mock_success = MagicMock()
        mock_success.choices = [MagicMock()]
        mock_success.choices[0].message.content = "Success after retry"
        mock_success.usage = MagicMock()
        mock_success.usage.prompt_tokens = 5
        mock_success.usage.completion_tokens = 5
        mock_success.usage.total_tokens = 10
        mock_success._hidden_params = {}

        with patch(
            "src.ai.infrastructure.llm.litellm_provider.litellm.completion",
            side_effect=[rate_limit_err, mock_success],
        ) as mock_completion:
            request = LLMRequest(prompt="test")
            result = provider.complete(request)

            assert mock_completion.call_count == 2
            assert result.content == "Success after retry"

    def test_auth_error_not_retried(self, provider):
        """Provider does NOT retry on 401 auth errors."""
        import httpx
        from litellm import AuthenticationError

        auth_err = AuthenticationError(
            message="invalid key",
            llm_provider="openai",
            model="gpt-4o-mini",
            response=httpx.Response(status_code=401, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")),
        )

        with patch(
            "src.ai.infrastructure.llm.litellm_provider.litellm.completion",
            side_effect=auth_err,
        ) as mock_completion:
            request = LLMRequest(prompt="test")

            with pytest.raises(AuthenticationError):
                provider.complete(request)

            assert mock_completion.call_count == 1  # Only one call, no retry


class TestLiteLLMProviderSwitching:
    """Test provider switching."""

    def test_set_provider(self, provider):
        """Provider can switch between providers."""
        assert provider._provider == "openai"
        provider.set_provider("claude")
        assert provider._provider == "claude"
        provider.set_provider("gemini")
        assert provider._provider == "gemini"
