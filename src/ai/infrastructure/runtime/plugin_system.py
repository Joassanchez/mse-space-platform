"""Plugin System for the AI ecosystem (Módulo 4).

Discovers agents via manifest glob, validates manifests against JSON Schema,
and manages agent registration.
"""

import glob
import logging
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from src.ai.domain.errors import ManifestValidationError
from src.ai.domain.models import AgentManifest, ExecutionLimits

logger = logging.getLogger(__name__)

# JSON Schema for agent manifest validation
MANIFEST_SCHEMA = {
    "type": "object",
    "required": ["name", "version", "entry_point", "description", "tools", "output_schema"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "entry_point": {"type": "string", "pattern": r"^[a-zA-Z_][a-zA-Z0-9_]*:[a-zA-Z_][a-zA-Z0-9_]*$"},
        "description": {"type": "string", "minLength": 1},
        "type": {"type": "string"},
        "tools": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 0,
        },
        "limits": {
            "type": "object",
            "properties": {
                "max_steps": {"type": "integer", "minimum": 1},
                "max_tokens": {"type": "integer", "minimum": 1},
                "timeout_seconds": {"type": "integer", "minimum": 1},
            },
        },
        "output_schema": {
            "type": "object",
            "required": ["type"],
        },
    },
    "additionalProperties": False,
}


class PluginSystem:
    """Discovers, validates, and registers agent plugins.

    Agents are discovered by globbing for manifest.yaml files in the
    configured agents directory. Each manifest is validated against
    a JSON Schema before the agent is registered.
    """

    def __init__(self, agents_dir: str = "src/ai/agents"):
        """Initialize the plugin system.

        Args:
            agents_dir: Root directory for agent discovery.
        """
        self._agents_dir = Path(agents_dir)
        self._registered: dict[str, AgentManifest] = {}

    def discover(self) -> list[Path]:
        """Discover all agent manifests in the agents directory.

        Globs for src/ai/agents/*/manifest.yaml.

        Returns:
            List of paths to valid manifest.yaml files.
        """
        pattern = str(self._agents_dir / "*" / "manifest.yaml")
        manifests = sorted(glob.glob(pattern))
        logger.info(f"Discovered {len(manifests)} agent manifest(s) in {self._agents_dir}")
        return [Path(p) for p in manifests]

    def validate_manifest(self, manifest_path: Path) -> dict[str, Any]:
        """Validate an agent manifest against the JSON Schema.

        Args:
            manifest_path: Path to the manifest.yaml file.

        Returns:
            Parsed manifest dict if valid.

        Raises:
            ManifestValidationError: If the manifest is invalid.
            FileNotFoundError: If the manifest file does not exist.
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ManifestValidationError(
                f"Manifest {manifest_path} is not a valid YAML object"
            )

        if not HAS_JSONSCHEMA:
            # Basic validation without jsonschema
            required = ["name", "version", "entry_point", "description", "tools", "output_schema"]
            missing = [k for k in required if k not in raw]
            if missing:
                raise ManifestValidationError(
                    f"Manifest {manifest_path} missing required fields: {', '.join(missing)}"
                )
            return raw

        # Full JSON Schema validation
        try:
            jsonschema.validate(instance=raw, schema=MANIFEST_SCHEMA)
        except jsonschema.ValidationError as e:
            raise ManifestValidationError(
                f"Manifest {manifest_path} validation failed: {e.message}"
            ) from e

        return raw

    def parse_manifest(self, raw: dict[str, Any]) -> AgentManifest:
        """Parse a validated manifest dict into an AgentManifest dataclass.

        Args:
            raw: Validated manifest dict from validate_manifest().

        Returns:
            AgentManifest dataclass instance.
        """
        limits_raw = raw.get("limits", {})
        limits = ExecutionLimits(
            max_steps=limits_raw.get("max_steps", 10),
            max_tokens=limits_raw.get("max_tokens", 4096),
            timeout_seconds=limits_raw.get("timeout_seconds", 30),
        )

        return AgentManifest(
            name=raw["name"],
            version=raw["version"],
            entry_point=raw["entry_point"],
            description=raw["description"],
            tools=raw.get("tools", []),
            limits=limits,
            output_schema=raw.get("output_schema", {}),
            agent_type=raw.get("type", "reference"),
        )

    def register(self, manifest: AgentManifest) -> None:
        """Register a validated agent manifest.

        Args:
            manifest: Validated AgentManifest to register.
        """
        self._registered[manifest.name] = manifest
        logger.info(f"Registered agent: {manifest.name} v{manifest.version}")

    def list_agents(self) -> list[AgentManifest]:
        """List all registered agents.

        Returns:
            List of registered AgentManifest objects.
        """
        return list(self._registered.values())

    def get_agent(self, name: str) -> AgentManifest | None:
        """Get a registered agent by name.

        Args:
            name: Agent name.

        Returns:
            AgentManifest if found, None otherwise.
        """
        return self._registered.get(name)

    def discover_and_register_all(self) -> list[AgentManifest]:
        """Discover, validate, and register all agents in the directory.

        Returns:
            List of successfully registered AgentManifest objects.
        """
        manifest_paths = self.discover()
        registered: list[AgentManifest] = []

        for path in manifest_paths:
            try:
                raw = self.validate_manifest(path)
                manifest = self.parse_manifest(raw)
                self.register(manifest)
                registered.append(manifest)
            except (ManifestValidationError, FileNotFoundError) as e:
                logger.warning(f"Skipping invalid manifest {path}: {e}")

        return registered
