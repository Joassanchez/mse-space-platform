"""Integration tests for AI Reference Agent runtime loading.

Tests:
- Runtime loads reference agent from manifest
- Agent executes with context mock
- Output validates against declared schema

Run with: pytest -m integration tests/ai/integration/test_reference_agent_runtime.py
"""

from pathlib import Path

import pytest
import yaml


def _validate_output(output: dict, schema: dict) -> list[str]:
    """Simple output validator against schema properties.

    Returns list of validation errors (empty = valid).
    """
    errors = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in output:
            errors.append(f"Missing required field: {field}")

    for field, value in output.items():
        if field in properties:
            expected_type = properties[field].get("type")
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Field '{field}' must be a string")
            elif expected_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"Field '{field}' must be a number")

    return errors


@pytest.mark.integration
class TestReferenceAgentRuntime:
    """Test reference agent loading and execution."""

    @pytest.fixture
    def manifest_path(self):
        """Path to the reference agent manifest."""
        return (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "ai"
            / "agents"
            / "reference_agent"
            / "manifest.yaml"
        )

    @pytest.fixture
    def manifest(self, manifest_path):
        """Load the reference agent manifest."""
        with open(manifest_path, "r") as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def agent(self, manifest_path):
        """Load the reference agent class."""
        import sys
        sys.path.insert(0, str(manifest_path.parent.parent.parent.parent))

        from src.ai.agents.reference_agent.agent import ReferenceAgent
        return ReferenceAgent()

    def test_agent_loads(self, agent):
        """Reference agent instantiates successfully."""
        assert agent is not None
        assert agent.name == "reference-agent"

    def test_agent_executes_with_context(self, agent):
        """Agent executes with mock context and returns structured output."""
        mock_context = {
            "regions": [{"id": 1, "name": "Test Region"}],
            "indicators": [{"indicator_code": "SM_INDEX", "value": 0.45}],
            "risk_assessments": [{"risk_type": "drought", "risk_level": "medium"}],
        }

        output = agent.execute(mock_context)

        assert "conclusion" in output
        assert "confidence" in output
        assert isinstance(output["conclusion"], str)
        assert isinstance(output["confidence"], (int, float))

    def test_agent_output_validates_against_schema(self, agent, manifest):
        """Agent output validates against the manifest's output_schema."""
        mock_context = {
            "regions": [{"id": 1, "name": "Test Region"}],
            "indicators": [],
            "risk_assessments": [],
        }

        output = agent.execute(mock_context)
        errors = _validate_output(output, manifest["output_schema"])

        assert errors == [], f"Output validation errors: {errors}"

    def test_agent_output_confidence_in_range(self, agent, manifest):
        """Agent output confidence is within 0-1 range."""
        mock_context = {"regions": [], "indicators": [], "risk_assessments": []}
        output = agent.execute(mock_context)

        schema = manifest["output_schema"]["properties"]["confidence"]
        assert schema["minimum"] <= output["confidence"] <= schema["maximum"]
