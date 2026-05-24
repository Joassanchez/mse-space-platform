"""Unit tests for Plugin System.

Tests:
- Manifest discovery via glob
- JSON Schema validation (valid and invalid manifests)
- Agent registration and listing
- discover_and_register_all workflow
- Missing required fields rejection
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.ai.domain.errors import ManifestValidationError
from src.ai.infrastructure.runtime.plugin_system import PluginSystem, MANIFEST_SCHEMA


VALID_MANIFEST = {
    "name": "test-agent",
    "version": "1.0.0",
    "entry_point": "agent:TestAgent",
    "description": "A test agent",
    "tools": ["geospatial_query"],
    "output_schema": {
        "type": "object",
        "required": ["conclusion"],
        "properties": {"conclusion": {"type": "string"}},
    },
    "limits": {
        "max_steps": 10,
        "max_tokens": 4096,
        "timeout_seconds": 30,
    },
}


@pytest.fixture
def agents_dir():
    """Create a temporary agents directory with a valid manifest."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent_dir = Path(tmpdir) / "test-agent"
        agent_dir.mkdir()
        manifest_path = agent_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(VALID_MANIFEST, f)
        yield Path(tmpdir)


@pytest.fixture
def plugin_system(agents_dir):
    """Create PluginSystem pointing to temp agents directory."""
    return PluginSystem(agents_dir=str(agents_dir))


class TestPluginSystemDiscovery:
    """Test manifest discovery."""

    def test_discover_finds_manifests(self, plugin_system, agents_dir):
        """discover returns paths to manifest.yaml files."""
        manifests = plugin_system.discover()

        assert len(manifests) == 1
        assert manifests[0].name == "manifest.yaml"

    def test_discover_empty_directory(self):
        """discover returns empty list for directory with no manifests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ps = PluginSystem(agents_dir=tmpdir)
            assert ps.discover() == []


class TestPluginSystemValidation:
    """Test manifest JSON Schema validation."""

    def test_validate_valid_manifest(self, plugin_system, agents_dir):
        """Valid manifest passes validation."""
        manifest_path = agents_dir / "test-agent" / "manifest.yaml"
        result = plugin_system.validate_manifest(manifest_path)

        assert result["name"] == "test-agent"
        assert result["version"] == "1.0.0"

    def test_validate_missing_file_raises(self, plugin_system):
        """Missing manifest file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Manifest not found"):
            plugin_system.validate_manifest(Path("/nonexistent/manifest.yaml"))

    def test_validate_missing_name_raises(self, plugin_system, agents_dir):
        """Manifest without name raises ManifestValidationError."""
        agent_dir = agents_dir / "bad-agent"
        agent_dir.mkdir()
        manifest_path = agent_dir / "manifest.yaml"

        bad_manifest = {**VALID_MANIFEST}
        del bad_manifest["name"]

        with open(manifest_path, "w") as f:
            yaml.dump(bad_manifest, f)

        with pytest.raises(ManifestValidationError, match="name"):
            plugin_system.validate_manifest(manifest_path)

    def test_validate_invalid_version_format_raises(self, plugin_system, agents_dir):
        """Non-semver version raises ManifestValidationError."""
        agent_dir = agents_dir / "bad-version"
        agent_dir.mkdir()
        manifest_path = agent_dir / "manifest.yaml"

        bad_manifest = {**VALID_MANIFEST, "version": "not-a-version"}

        with open(manifest_path, "w") as f:
            yaml.dump(bad_manifest, f)

        with pytest.raises(ManifestValidationError, match="version"):
            plugin_system.validate_manifest(manifest_path)

    def test_validate_invalid_entry_point_raises(self, plugin_system, agents_dir):
        """Malformed entry_point raises ManifestValidationError."""
        agent_dir = agents_dir / "bad-entry"
        agent_dir.mkdir()
        manifest_path = agent_dir / "manifest.yaml"

        bad_manifest = {**VALID_MANIFEST, "entry_point": "no-colon-here"}

        with open(manifest_path, "w") as f:
            yaml.dump(bad_manifest, f)

        with pytest.raises(ManifestValidationError):
            plugin_system.validate_manifest(manifest_path)

    def test_validate_without_jsonschema_fallback(self, agents_dir):
        """Without jsonschema, basic validation still works."""
        with patch("src.ai.infrastructure.runtime.plugin_system.HAS_JSONSCHEMA", False):
            ps = PluginSystem(agents_dir=str(agents_dir))
            manifest_path = agents_dir / "test-agent" / "manifest.yaml"
            result = ps.validate_manifest(manifest_path)
            assert result["name"] == "test-agent"


class TestPluginSystemRegistration:
    """Test agent registration."""

    def test_register_and_list(self, plugin_system):
        """register adds agent, list_agents returns it."""
        from src.ai.domain.models import AgentManifest, ExecutionLimits

        manifest = AgentManifest(
            name="registered-agent",
            version="1.0.0",
            entry_point="agent:TestAgent",
            description="Test",
            tools=[],
            limits=ExecutionLimits(),
            output_schema={"type": "object"},
        )

        plugin_system.register(manifest)
        agents = plugin_system.list_agents()

        assert len(agents) == 1
        assert agents[0].name == "registered-agent"

    def test_get_agent_by_name(self, plugin_system):
        """get_agent returns manifest by name."""
        from src.ai.domain.models import AgentManifest, ExecutionLimits

        manifest = AgentManifest(
            name="lookup-agent",
            version="1.0.0",
            entry_point="agent:TestAgent",
            description="Test",
            tools=[],
            limits=ExecutionLimits(),
            output_schema={"type": "object"},
        )

        plugin_system.register(manifest)
        found = plugin_system.get_agent("lookup-agent")

        assert found is not None
        assert found.name == "lookup-agent"

    def test_get_agent_not_found(self, plugin_system):
        """get_agent returns None for unknown name."""
        assert plugin_system.get_agent("nonexistent") is None


class TestPluginSystemDiscoverAndRegister:
    """Test full discover-validate-register workflow."""

    def test_discover_and_register_all(self, plugin_system, agents_dir):
        """discover_and_register_all finds, validates, and registers."""
        registered = plugin_system.discover_and_register_all()

        assert len(registered) == 1
        assert registered[0].name == "test-agent"
        assert len(plugin_system.list_agents()) == 1

    def test_discover_and_register_all_skips_invalid(self, plugin_system, agents_dir):
        """Invalid manifests are skipped with a warning."""
        # Create an invalid manifest
        bad_dir = agents_dir / "bad-agent"
        bad_dir.mkdir()
        with open(bad_dir / "manifest.yaml", "w") as f:
            yaml.dump({"name": "bad"}, f)  # Missing required fields

        registered = plugin_system.discover_and_register_all()

        # Only the valid one should be registered
        assert len(registered) == 1
        assert registered[0].name == "test-agent"


class TestPluginSystemParseManifest:
    """Test manifest parsing to dataclass."""

    def test_parse_manifest(self, plugin_system):
        """parse_manifest converts dict to AgentManifest."""
        raw = {
            "name": "parsed-agent",
            "version": "2.0.0",
            "entry_point": "agent:ParsedAgent",
            "description": "Parsed test",
            "tools": ["tool1"],
            "limits": {"max_steps": 5},
            "output_schema": {"type": "object"},
        }

        manifest = plugin_system.parse_manifest(raw)

        assert manifest.name == "parsed-agent"
        assert manifest.version == "2.0.0"
        assert manifest.limits.max_steps == 5
        assert manifest.limits.max_tokens == 4096  # default
        assert manifest.agent_type == "reference"  # default
