"""Unit tests for Response Consolidator.

Tests:
- Single agent output passthrough
- Multi-agent confidence-weighted merging
- Conflict detection (high-confidence agents with different conclusions)
- Empty input handling
- Provenance tracking
"""

import pytest

from src.ai.application.response_consolidator import ResponseConsolidator


@pytest.fixture
def consolidator():
    """Create ResponseConsolidator."""
    return ResponseConsolidator()


class TestConsolidatorEmptyInput:
    """Test empty input handling."""

    def test_empty_outputs(self, consolidator):
        """Empty agent_outputs returns default response."""
        result = consolidator.consolidate([])

        assert result["confidence"] == 0.0
        assert result["conclusion"] == "No agent outputs to consolidate."
        assert result["conflicts"] == []


class TestConsolidatorSingleAgent:
    """Test single agent output."""

    def test_single_agent_passthrough(self, consolidator):
        """Single agent output is returned as-is with provenance."""
        outputs = [{"conclusion": "Single agent result", "confidence": 0.8}]

        result = consolidator.consolidate(outputs, agent_ids=["agent-1"])

        assert result["conclusion"] == "Single agent result"
        assert result["confidence"] == 0.8
        assert len(result["agent_contributions"]) == 1
        assert result["agent_contributions"][0]["agent_id"] == "agent-1"


class TestConsolidatorMultiAgent:
    """Test multi-agent merging."""

    def test_weighted_average_confidence(self, consolidator):
        """Confidence is weighted average of all agents."""
        outputs = [
            {"conclusion": "Result A", "confidence": 0.9},
            {"conclusion": "Result B", "confidence": 0.5},
            {"conclusion": "Result C", "confidence": 0.7},
        ]

        result = consolidator.consolidate(
            outputs, agent_ids=["a", "b", "c"]
        )

        # Average: (0.9 + 0.5 + 0.7) / 3 = 0.7
        assert result["confidence"] == pytest.approx(0.7, rel=0.01)

    def test_merged_conclusion_attributes_agents(self, consolidator):
        """Multi-agent conclusion attributes each part to its agent."""
        outputs = [
            {"conclusion": "Result A", "confidence": 0.9},
            {"conclusion": "Result B", "confidence": 0.5},
        ]

        result = consolidator.consolidate(
            outputs, agent_ids=["agent-a", "agent-b"]
        )

        assert "[agent-a]" in result["conclusion"]
        assert "[agent-b]" in result["conclusion"]
        assert "Result A" in result["conclusion"]
        assert "Result B" in result["conclusion"]

    def test_agent_contributions_include_raw_output(self, consolidator):
        """Contributions include the full raw output."""
        outputs = [
            {
                "conclusion": "Result A",
                "confidence": 0.9,
                "extra_field": "extra data",
            }
        ]

        result = consolidator.consolidate(outputs, agent_ids=["a"])

        assert result["agent_contributions"][0]["raw_output"]["extra_field"] == "extra data"


class TestConsolidatorConflictDetection:
    """Test conflict detection."""

    def test_no_conflict_same_conclusion(self, consolidator):
        """No conflict when conclusions match."""
        outputs = [
            {"conclusion": "Same result", "confidence": 0.9},
            {"conclusion": "Same result", "confidence": 0.8},
        ]

        result = consolidator.consolidate(outputs, agent_ids=["a", "b"])

        assert result["conflicts"] == []

    def test_no_conflict_low_confidence(self, consolidator):
        """No conflict when agents have low confidence (below 0.7)."""
        outputs = [
            {"conclusion": "Result A", "confidence": 0.5},
            {"conclusion": "Result B", "confidence": 0.4},
        ]

        result = consolidator.consolidate(outputs, agent_ids=["a", "b"])

        assert result["conflicts"] == []

    def test_conflict_high_confidence_different_conclusions(self, consolidator):
        """Conflict flagged when high-confidence agents disagree."""
        outputs = [
            {"conclusion": "Result A", "confidence": 0.9},
            {"conclusion": "Result B", "confidence": 0.8},
        ]

        result = consolidator.consolidate(outputs, agent_ids=["a", "b"])

        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["type"] == "conclusion_mismatch"
        assert "a" in result["conflicts"][0]["agents"]
        assert "b" in result["conflicts"][0]["agents"]

    def test_conflict_includes_agent_ids(self, consolidator):
        """Conflict includes the conflicting agent IDs."""
        outputs = [
            {"conclusion": "X", "confidence": 0.9},
            {"conclusion": "Y", "confidence": 0.85},
            {"conclusion": "Z", "confidence": 0.3},  # Low confidence, not involved
        ]

        result = consolidator.consolidate(
            outputs, agent_ids=["high-1", "high-2", "low-1"]
        )

        # Only high-confidence agents should be in conflicts
        conflict_agents = result["conflicts"][0]["agents"]
        assert "high-1" in conflict_agents
        assert "high-2" in conflict_agents
        assert "low-1" not in conflict_agents


class TestConsolidatorAutoAgentIds:
    """Test auto-generated agent IDs."""

    def test_auto_ids_when_not_provided(self, consolidator):
        """Agent IDs are auto-generated when not provided."""
        outputs = [
            {"conclusion": "A", "confidence": 0.5},
            {"conclusion": "B", "confidence": 0.6},
        ]

        result = consolidator.consolidate(outputs)

        assert result["agent_contributions"][0]["agent_id"] == "agent_0"
        assert result["agent_contributions"][1]["agent_id"] == "agent_1"
