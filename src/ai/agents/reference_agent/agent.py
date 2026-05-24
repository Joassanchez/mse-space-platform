"""Reference Agent — minimal fixture for validating the runtime.

This agent has NO domain logic. It receives context, produces a trivial
structured output, and exists solely to validate that the runtime can:
- Load agents from manifests
- Execute agents with context
- Validate outputs against declared schemas
"""

from typing import Any


class ReferenceAgent:
    """Minimal reference agent for runtime validation.

    Receives structured context and produces a trivial output with
    a conclusion and confidence score. No geospatial or domain logic.
    """

    def __init__(self) -> None:
        """Initialize the reference agent."""
        self.name = "reference-agent"

    def execute(self, context: dict, **kwargs: Any) -> dict:
        """Execute the agent with provided context.

        Args:
            context: Structured context from the Context Engine.
            **kwargs: Additional runtime parameters.

        Returns:
            Dict matching the output_schema:
                - conclusion: string summary
                - confidence: float 0-1
        """
        region_count = len(context.get("regions", []))
        indicator_count = len(context.get("indicators", []))
        risk_count = len(context.get("risk_assessments", []))

        conclusion = (
            f"Reference agent processed context: "
            f"{region_count} region(s), "
            f"{indicator_count} indicator(s), "
            f"{risk_count} risk assessment(s)."
        )

        return {
            "conclusion": conclusion,
            "confidence": 0.5,  # Fixed confidence for reference agent
        }
