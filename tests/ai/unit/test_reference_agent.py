"""Unit tests for Reference Agent manifest validation.

Tests:
- Manifest loads correctly from YAML
- Manifest validates against expected JSON Schema
- Required fields are present
- Output schema is valid
"""

import json
from pathlib import Path

import pytest
import yaml

# JSON Schema for agent manifest validation
MANIFEST_SCHEMA = {
    "type": "object",
    "required": ["name", "version", "entry_point", "description", "tools", "limits", "output_schema"],
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "entry_point": {"type": "string"},
        "description": {"type": "string"},
        "type": {"type": "string"},
        "tools": {
            "type": "array",
            "items": {"type": "string"},
        },
        "limits": {
            "type": "object",
            "required": ["max_steps", "max_tokens", "timeout_seconds"],
            "properties": {
                "max_steps": {"type": "integer", "minimum": 1},
                "max_tokens": {"type": "integer", "minimum": 1},
                "timeout_seconds": {"type": "integer", "minimum": 1},
            },
        },
        "output_schema": {
            "type": "object",
            "required": ["type", "properties"],
            "properties": {
                "type": {"type": "string"},
                "required": {"type": "array"},
                "properties": {"type": "object"},
            },
        },
    },
}


def _validate_manifest(manifest: dict, schema: dict) -> list[str]:
    """Simple JSON Schema validator (no jsonschema dependency needed for basic checks).

    Returns list of validation errors (empty = valid).
    """
    errors = []

    # Check required fields
    for field in schema.get("required", []):
        if field not in manifest:
            errors.append(f"Missing required field: {field}")

    # Check types for known properties
    props = schema.get("properties", {})
    for key, value in manifest.items():
        if key in props:
            expected_type = props[key].get("type")
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Field '{key}' must be a string")
            elif expected_type == "array" and not isinstance(value, list):
                errors.append(f"Field '{key}' must be an array")
            elif expected_type == "object" and not isinstance(value, dict):
                errors.append(f"Field '{key}' must be an object")
            elif expected_type == "integer" and not isinstance(value, int):
                errors.append(f"Field '{key}' must be an integer")

    # Validate nested objects
    if "limits" in manifest and isinstance(manifest["limits"], dict):
        limits_schema = schema["properties"]["limits"]
        for field in limits_schema.get("required", []):
            if field not in manifest["limits"]:
                errors.append(f"Missing required limits field: {field}")

    if "output_schema" in manifest and isinstance(manifest["output_schema"], dict):
        output_schema = schema["properties"]["output_schema"]
        for field in output_schema.get("required", []):
            if field not in manifest["output_schema"]:
                errors.append(f"Missing required output_schema field: {field}")

    return errors


@pytest.fixture
def manifest_path():
    """Path to the reference agent manifest."""
    return Path(__file__).parent.parent.parent.parent / "src" / "ai" / "agents" / "reference_agent" / "manifest.yaml"


@pytest.fixture
def manifest(manifest_path):
    """Load the reference agent manifest."""
    with open(manifest_path, "r") as f:
        return yaml.safe_load(f)


class TestManifestValidation:
    """Test manifest structure and validation."""

    def test_manifest_loads(self, manifest):
        """Manifest loads as valid YAML."""
        assert manifest is not None
        assert isinstance(manifest, dict)

    def test_manifest_has_required_fields(self, manifest):
        """Manifest contains all required fields."""
        required = ["name", "version", "entry_point", "description", "tools", "limits", "output_schema"]
        for field in required:
            assert field in manifest, f"Missing required field: {field}"

    def test_manifest_validates_against_schema(self, manifest):
        """Manifest passes JSON Schema validation."""
        errors = _validate_manifest(manifest, MANIFEST_SCHEMA)
        assert errors == [], f"Validation errors: {errors}"

    def test_manifest_type_is_reference(self, manifest):
        """Manifest type is 'reference'."""
        assert manifest.get("type") == "reference"

    def test_manifest_has_tool_allowlist(self, manifest):
        """Manifest declares allowed tools."""
        assert "tools" in manifest
        assert len(manifest["tools"]) > 0
        assert "geospatial_query" in manifest["tools"]

    def test_manifest_limits_are_valid(self, manifest):
        """Manifest limits have valid values."""
        limits = manifest["limits"]
        assert limits["max_steps"] >= 1
        assert limits["max_tokens"] >= 1
        assert limits["timeout_seconds"] >= 1

    def test_manifest_output_schema_has_required_fields(self, manifest):
        """Output schema declares required fields."""
        output_schema = manifest["output_schema"]
        assert "required" in output_schema
        assert "conclusion" in output_schema["required"]
        assert "confidence" in output_schema["required"]

    def test_manifest_output_schema_properties_valid(self, manifest):
        """Output schema properties are well-formed."""
        props = manifest["output_schema"]["properties"]
        assert "conclusion" in props
        assert props["conclusion"]["type"] == "string"
        assert "confidence" in props
        assert props["confidence"]["type"] == "number"


class TestManifestInvalid:
    """Test validation rejects invalid manifests."""

    def test_missing_name_fails(self):
        """Manifest without name fails validation."""
        manifest = {
            "version": "1.0.0",
            "entry_point": "agent:TestAgent",
            "description": "Test",
            "tools": [],
            "limits": {"max_steps": 10, "max_tokens": 1000, "timeout_seconds": 30},
            "output_schema": {"type": "object", "properties": {}},
        }
        errors = _validate_manifest(manifest, MANIFEST_SCHEMA)
        assert any("name" in e for e in errors)

    def test_missing_limits_fails(self):
        """Manifest without limits fails validation."""
        manifest = {
            "name": "test",
            "version": "1.0.0",
            "entry_point": "agent:TestAgent",
            "description": "Test",
            "tools": [],
            "output_schema": {"type": "object", "properties": {}},
        }
        errors = _validate_manifest(manifest, MANIFEST_SCHEMA)
        assert any("limits" in e for e in errors)

    def test_missing_output_schema_fails(self):
        """Manifest without output_schema fails validation."""
        manifest = {
            "name": "test",
            "version": "1.0.0",
            "entry_point": "agent:TestAgent",
            "description": "Test",
            "tools": [],
            "limits": {"max_steps": 10, "max_tokens": 1000, "timeout_seconds": 30},
        }
        errors = _validate_manifest(manifest, MANIFEST_SCHEMA)
        assert any("output_schema" in e for e in errors)
