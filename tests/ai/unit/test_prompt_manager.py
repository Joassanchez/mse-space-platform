"""Unit tests for Prompt Manager.

Tests:
- File loading from data/prompts/
- Variable injection with {{variable}} syntax
- MissingVariableWarning for undefined variables
- Front-matter parsing
- Template listing and reloading
- Cache behavior
"""

import tempfile
import warnings
from pathlib import Path

import pytest

from src.ai.infrastructure.prompts.prompt_manager import (
    PromptManager,
    MissingVariableWarning,
)


@pytest.fixture
def prompts_dir():
    """Create a temporary prompts directory with test templates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompts_path = Path(tmpdir)

        # Create maestro prompt
        maestro = prompts_path / "maestro.md"
        maestro.write_text(
            """---
version: v1
description: System prompt for all agents
expected_variables: region_name, analysis_type
---
# AI Assistant

You are analyzing {{region_name}} for {{analysis_type}}.

Follow these rules:
1. Be concise
2. Use data-driven conclusions
"""
        )

        # Create region analysis prompt
        region_prompt = prompts_path / "region_analysis.md"
        region_prompt.write_text(
            "Analyze region {{region_name}} with indicators: {{indicators}}"
        )

        # Create prompt without front-matter
        simple_prompt = prompts_path / "simple.md"
        simple_prompt.write_text("Hello, {{name}}!")

        yield prompts_path


@pytest.fixture
def manager(prompts_dir):
    """Create PromptManager pointing to temp directory."""
    return PromptManager(prompts_dir=str(prompts_dir))


class TestPromptManagerLoading:
    """Test template file loading."""

    def test_load_template(self, manager):
        """load returns template content."""
        content = manager.load("maestro")

        assert "# AI Assistant" in content
        assert "{{region_name}}" in content

    def test_load_missing_template_raises(self, manager):
        """load raises FileNotFoundError for unknown template."""
        with pytest.raises(FileNotFoundError, match="not found"):
            manager.load("nonexistent")

    def test_load_caches_content(self, manager):
        """load caches content after first read."""
        content1 = manager.load("simple")
        content2 = manager.load("simple")

        assert content1 == content2
        assert "simple" in manager._cache

    def test_list_templates(self, manager):
        """list_templates returns sorted template names."""
        templates = manager.list_templates()

        assert "maestro" in templates
        assert "region_analysis" in templates
        assert "simple" in templates
        assert templates == sorted(templates)


class TestPromptManagerRendering:
    """Test variable injection."""

    def test_render_with_all_variables(self, manager):
        """render substitutes all defined variables."""
        result = manager.render(
            "region_analysis",
            variables={
                "region_name": "Buenos Aires",
                "indicators": "SM_INDEX, NDVI",
            },
        )

        assert "Buenos Aires" in result
        assert "SM_INDEX, NDVI" in result
        assert "{{" not in result  # No remaining placeholders

    def test_render_missing_variable_warns(self, manager):
        """render warns when variable is undefined."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = manager.render("simple", variables={})

        assert len(w) == 1
        assert issubclass(w[0].category, MissingVariableWarning)
        assert "name" in str(w[0].message)
        # Placeholder remains in output
        assert "{{name}}" in result

    def test_render_partial_variables(self, manager):
        """render substitutes defined vars, warns for undefined."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = manager.render(
                "region_analysis",
                variables={"region_name": "Cordoba"},
            )

        # region_name substituted
        assert "Cordoba" in result
        # indicators still a placeholder
        assert "{{indicators}}" in result
        # Warning for indicators
        assert any("indicators" in str(warning.message) for warning in w)


class TestPromptManagerMetadata:
    """Test front-matter parsing."""

    def test_get_metadata(self, manager):
        """get_metadata returns parsed front-matter."""
        metadata = manager.get_metadata("maestro")

        assert metadata["version"] == "v1"
        assert metadata["description"] == "System prompt for all agents"

    def test_get_metadata_no_frontmatter(self, manager):
        """get_metadata returns empty dict for templates without front-matter."""
        metadata = manager.get_metadata("simple")

        assert metadata == {}

    def test_get_metadata_caches(self, manager):
        """get_metadata caches parsed metadata."""
        metadata1 = manager.get_metadata("maestro")
        metadata2 = manager.get_metadata("maestro")

        assert metadata1 == metadata2
        assert "maestro" in manager._metadata


class TestPromptManagerReload:
    """Test cache reloading."""

    def test_reload_all(self, manager):
        """reload clears all caches."""
        manager.load("maestro")
        manager.get_metadata("maestro")

        manager.reload()

        assert manager._cache == {}
        assert manager._metadata == {}

    def test_reload_single_template(self, manager):
        """reload with template_name clears only that template."""
        manager.load("maestro")
        manager.load("simple")

        manager.reload("maestro")

        assert "maestro" not in manager._cache
        assert "simple" in manager._cache


class TestPromptManagerMissingDirectory:
    """Test behavior when prompts directory doesn't exist."""

    def test_missing_directory_warns(self, caplog):
        """PromptManager warns when directory doesn't exist."""
        import logging

        with caplog.at_level(logging.WARNING):
            manager = PromptManager(prompts_dir="/nonexistent/prompts")

        assert any("not found" in record.message for record in caplog.records)
        assert manager.list_templates() == []
