"""LLM tools for the AI ecosystem (Módulo 4).

Wrappers over LLMProvider for use by agents:
- SummarizationTool: summarizes text via LLM
- StructuredOutputTool: produces structured JSON output via LLM
"""

import json
import logging
from typing import Any

from src.ai.domain.interfaces import LLMProvider, Tool
from src.ai.domain.models import LLMRequest, ToolResult

logger = logging.getLogger(__name__)


class SummarizationTool(Tool):
    """Summarizes text content via the LLM provider.

    Agents use this to condense long context or produce executive summaries.
    """

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "summarization"

    def __init__(
        self,
        llm_provider: LLMProvider,
        model: str | None = None,
        max_tokens: int = 512,
    ):
        """Initialize the Summarization Tool.

        Args:
            llm_provider: LLMProvider instance for generating summaries.
            model: Optional model override.
            max_tokens: Maximum tokens in the summary.
        """
        self._llm = llm_provider
        self._model = model
        self._max_tokens = max_tokens

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute text summarization.

        Required kwargs:
        - text: Text content to summarize.

        Optional kwargs:
        - instruction: Custom summarization instruction.
        - max_tokens: Override max tokens for this call.

        Args:
            **kwargs: Summarization parameters.

        Returns:
            ToolResult with summarized text or error.
        """
        text = kwargs.get("text")
        if not text:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="No text provided for summarization",
            )

        instruction = kwargs.get(
            "instruction",
            "Summarize the following text concisely, preserving key facts and numbers.",
        )
        max_tokens = kwargs.get("max_tokens", self._max_tokens)

        try:
            request = LLMRequest(
                prompt=f"{instruction}\n\nText to summarize:\n{text}",
                model=self._model,
                max_tokens=max_tokens,
                temperature=0.3,  # Lower temperature for summarization
            )

            response = self._llm.complete(request)

            return ToolResult(
                tool_name=self.name,
                success=True,
                data={
                    "summary": response.content,
                    "model": response.model,
                    "tokens_used": response.usage.get("total_tokens", 0),
                },
            )

        except Exception as e:
            logger.error(f"SummarizationTool failed: {e}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
            )


class StructuredOutputTool(Tool):
    """Produces structured JSON output via the LLM provider.

    Agents use this when they need to generate data in a specific schema
    (e.g., classification, scoring, extraction).
    """

    @property
    def name(self) -> str:
        """Tool identifier."""
        return "structured_output"

    def __init__(
        self,
        llm_provider: LLMProvider,
        model: str | None = None,
    ):
        """Initialize the Structured Output Tool.

        Args:
            llm_provider: LLMProvider instance for generating structured output.
            model: Optional model override.
        """
        self._llm = llm_provider
        self._model = model

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute structured output generation.

        Required kwargs:
        - prompt: The prompt/question for the LLM.
        - schema_description: Description of the expected output schema.

        Optional kwargs:
        - context: Additional context to include.
        - schema: JSON Schema for the expected output (for validation hint).

        Args:
            **kwargs: Structured output parameters.

        Returns:
            ToolResult with parsed JSON output or error.
        """
        prompt = kwargs.get("prompt")
        if not prompt:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="No prompt provided for structured output",
            )

        schema_desc = kwargs.get(
            "schema_description",
            "Return a JSON object with the requested fields.",
        )

        system_prompt = (
            f"You must respond with valid JSON only. {schema_desc}\n"
            "Do not include any text before or after the JSON object."
        )

        try:
            request = LLMRequest(
                prompt=prompt,
                context=system_prompt,
                model=self._model,
                max_tokens=1024,
                temperature=0.1,  # Very low temperature for structured output
            )

            response = self._llm.complete(request)

            # Parse JSON from response
            content = response.content.strip()
            # Handle markdown code blocks if present
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            parsed = json.loads(content)

            return ToolResult(
                tool_name=self.name,
                success=True,
                data=parsed,
            )

        except json.JSONDecodeError as e:
            logger.error(f"StructuredOutputTool: invalid JSON: {e}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"LLM returned invalid JSON: {e}",
            )
        except Exception as e:
            logger.error(f"StructuredOutputTool failed: {e}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
            )
