"""Unit tests for AI tools (geospatial and LLM tools).

Tests:
- Geospatial tools: RegionQueryTool, IndicatorLookupTool, RiskAssessmentTool
  (mocked repos)
- LLM tools: SummarizationTool, StructuredOutputTool (mocked LLMProvider)
- Tool error handling
- Tool name properties
"""

from unittest.mock import MagicMock

import pytest

from src.ai.domain.models import ToolResult
from src.ai.infrastructure.tools.geospatial_tools import (
    RegionQueryTool,
    IndicatorLookupTool,
    RiskAssessmentTool,
)
from src.ai.infrastructure.tools.llm_tools import (
    SummarizationTool,
    StructuredOutputTool,
)


# ============================================================
# Geospatial Tools
# ============================================================


class TestRegionQueryTool:
    """Test RegionQueryTool."""

    @pytest.fixture
    def tool(self):
        """Create RegionQueryTool with mock repo."""
        repo = MagicMock()
        return RegionQueryTool(region_repo=repo)

    def test_name(self, tool):
        """Tool name is 'geospatial_query'."""
        assert tool.name == "geospatial_query"

    def test_execute_get_by_id_success(self, tool):
        """get_by_id returns serialized region data."""
        mock_region = MagicMock()
        mock_region.id = 1
        mock_region.name = "Test Region"
        mock_region.region_type = "administrative"
        mock_region.country = "Argentina"
        mock_region.province = "Buenos Aires"
        mock_region.area_km2 = 10000.0
        tool._repo.get_by_id.return_value = mock_region

        result = tool.execute(region_id=1)

        assert result.success is True
        assert result.data["id"] == 1
        assert result.data["name"] == "Test Region"

    def test_execute_get_by_id_not_found(self, tool):
        """get_by_id returns failure when region not found."""
        tool._repo.get_by_id.return_value = None

        result = tool.execute(region_id=999)

        assert result.success is False
        assert "not found" in result.error

    def test_execute_unknown_operation(self, tool):
        """Unknown operation returns error."""
        result = tool.execute(unknown_param="test")

        assert result.success is False
        assert "Unknown operation" in result.error

    def test_execute_exception_returns_error(self, tool):
        """Database exception returns error ToolResult."""
        tool._repo.get_by_id.side_effect = Exception("DB error")

        result = tool.execute(region_id=1)

        assert result.success is False
        assert result.error == "DB error"


class TestIndicatorLookupTool:
    """Test IndicatorLookupTool."""

    @pytest.fixture
    def tool(self):
        """Create IndicatorLookupTool with mock repo."""
        repo = MagicMock()
        return IndicatorLookupTool(indicator_repo=repo)

    def test_name(self, tool):
        """Tool name is 'indicator_lookup'."""
        assert tool.name == "indicator_lookup"

    def test_execute_find_by_region_success(self, tool):
        """find_by_region returns serialized indicators."""
        mock_ind = MagicMock()
        mock_ind.id = 1
        mock_ind.region_id = 1
        mock_ind.indicator_code = "SM_INDEX"
        mock_ind.indicator_name = "Soil Moisture"
        mock_ind.value = 0.45
        mock_ind.unit = "m3/m3"
        mock_ind.classification = "normal"
        mock_ind.confidence = 0.8
        mock_ind.temporal_start = "2024-01-01"
        mock_ind.temporal_end = "2024-01-08"
        tool._repo.find_by_region.return_value = [mock_ind]

        result = tool.execute(region_id=1)

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["indicator_code"] == "SM_INDEX"

    def test_execute_unknown_operation(self, tool):
        """Unknown operation returns error."""
        result = tool.execute(unknown_param="test")

        assert result.success is False


class TestRiskAssessmentTool:
    """Test RiskAssessmentTool."""

    @pytest.fixture
    def tool(self):
        """Create RiskAssessmentTool with mock repo."""
        repo = MagicMock()
        return RiskAssessmentTool(risk_repo=repo)

    def test_name(self, tool):
        """Tool name is 'risk_assessment'."""
        assert tool.name == "risk_assessment"

    def test_execute_find_by_region_success(self, tool):
        """find_by_region returns serialized risk assessments."""
        mock_risk = MagicMock()
        mock_risk.id = 1
        mock_risk.region_id = 1
        mock_risk.risk_type = "drought"
        mock_risk.risk_level = "medium"
        mock_risk.risk_score = 0.5
        mock_risk.confidence = 0.7
        mock_risk.explanation = "Moderate drought risk"
        mock_risk.temporal_start = "2024-01-01"
        mock_risk.temporal_end = "2024-01-31"
        tool._repo.find_by_region_and_date.return_value = [mock_risk]

        result = tool.execute(region_id=1)

        assert result.success is True
        assert result.data[0]["risk_type"] == "drought"


# ============================================================
# LLM Tools
# ============================================================


class TestSummarizationTool:
    """Test SummarizationTool."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLMProvider."""
        from src.ai.domain.models import LLMResponse

        llm = MagicMock()
        llm.complete.return_value = LLMResponse(
            content="This is a summary.",
            model="gpt-4o-mini",
            usage={"total_tokens": 50},
        )
        return llm

    @pytest.fixture
    def tool(self, mock_llm):
        """Create SummarizationTool."""
        return SummarizationTool(llm_provider=mock_llm)

    def test_name(self, tool):
        """Tool name is 'summarization'."""
        assert tool.name == "summarization"

    def test_execute_success(self, tool):
        """execute returns summarized text."""
        result = tool.execute(text="Long text to summarize...")

        assert result.success is True
        assert result.data["summary"] == "This is a summary."
        assert result.data["model"] == "gpt-4o-mini"

    def test_execute_no_text(self, tool):
        """execute returns error when no text provided."""
        result = tool.execute()

        assert result.success is False
        assert "No text provided" in result.error

    def test_execute_custom_instruction(self, tool, mock_llm):
        """execute uses custom instruction when provided."""
        tool.execute(
            text="Test text",
            instruction="Summarize in one sentence",
        )

        call_args = mock_llm.complete.call_args
        request = call_args[0][0]
        assert "Summarize in one sentence" in request.prompt


class TestStructuredOutputTool:
    """Test StructuredOutputTool."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLMProvider."""
        from src.ai.domain.models import LLMResponse

        llm = MagicMock()
        llm.complete.return_value = LLMResponse(
            content='{"category": "drought", "score": 0.8}',
            model="gpt-4o-mini",
            usage={"total_tokens": 30},
        )
        return llm

    @pytest.fixture
    def tool(self, mock_llm):
        """Create StructuredOutputTool."""
        return StructuredOutputTool(llm_provider=mock_llm)

    def test_name(self, tool):
        """Tool name is 'structured_output'."""
        assert tool.name == "structured_output"

    def test_execute_success(self, tool):
        """execute returns parsed JSON."""
        result = tool.execute(
            prompt="Classify the risk",
            schema_description="Return category and score",
        )

        assert result.success is True
        assert result.data["category"] == "drought"
        assert result.data["score"] == 0.8

    def test_execute_no_prompt(self, tool):
        """execute returns error when no prompt provided."""
        result = tool.execute()

        assert result.success is False
        assert "No prompt provided" in result.error

    def test_execute_handles_markdown_code_blocks(self, mock_llm):
        """execute strips markdown code blocks from LLM response."""
        from src.ai.domain.models import LLMResponse

        mock_llm.complete.return_value = LLMResponse(
            content='```\n{"key": "value"}\n```',
            model="gpt-4o-mini",
        )
        tool = StructuredOutputTool(llm_provider=mock_llm)

        result = tool.execute(prompt="Test", schema_description="Test")

        assert result.success is True
        assert result.data == {"key": "value"}

    def test_execute_invalid_json(self, mock_llm):
        """execute returns error when LLM returns invalid JSON."""
        from src.ai.domain.models import LLMResponse

        mock_llm.complete.return_value = LLMResponse(
            content="not valid json",
            model="gpt-4o-mini",
        )
        tool = StructuredOutputTool(llm_provider=mock_llm)

        result = tool.execute(prompt="Test", schema_description="Test")

        assert result.success is False
        assert "invalid JSON" in result.error
