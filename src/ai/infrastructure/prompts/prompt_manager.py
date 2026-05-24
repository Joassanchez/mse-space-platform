"""Prompt Manager for the AI ecosystem (Módulo 4).

Loads prompt templates from versioned files in data/prompts/,
manages metadata, and supports variable injection with
MissingVariableWarning for undefined variables.

Storage strategy:
- Files (data/prompts/*.md) are the PRIMARY source of truth
- ai_prompt_metadata table is SECONDARY (production overrides only)
"""

import logging
import re
import warnings
from pathlib import Path
from typing import Any

from src.ai.domain.interfaces import PromptTemplate

logger = logging.getLogger(__name__)


class MissingVariableWarning(UserWarning):
    """Warning raised when a template variable has no corresponding value."""

    pass


class PromptManager(PromptTemplate):
    """Manages prompt templates from files with variable injection.

    Templates are stored as .md files in data/prompts/. The manager
    indexes them by filename (without extension) and supports
    variable injection using {{variable_name}} syntax.
    """

    def __init__(self, prompts_dir: str = "data/prompts"):
        """Initialize the Prompt Manager.

        Args:
            prompts_dir: Directory containing prompt template files.
        """
        self._prompts_dir = Path(prompts_dir)
        self._index: dict[str, Path] = {}
        self._cache: dict[str, str] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        self._build_index()

    def _build_index(self) -> None:
        """Index all prompt files in the prompts directory.

        Globs for *.md files and maps filename (without extension)
        to file path.
        """
        if not self._prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self._prompts_dir}")
            return

        for path in sorted(self._prompts_dir.glob("*.md")):
            if path.name == ".gitkeep":
                continue
            key = path.stem  # filename without extension
            self._index[key] = path
            logger.debug(f"Indexed prompt: {key} -> {path}")

    def load(self, template_name: str) -> str:
        """Load a prompt template by name.

        Checks the cache first, then reads from file.

        Args:
            template_name: Template identifier (e.g. "maestro", "region_analysis").

        Returns:
            Template text content.

        Raises:
            FileNotFoundError: If the template does not exist.
        """
        if template_name in self._cache:
            return self._cache[template_name]

        path = self._index.get(template_name)
        if path is None:
            # Try to rebuild index in case new files were added
            self._build_index()
            path = self._index.get(template_name)

        if path is None:
            raise FileNotFoundError(
                f"Prompt template '{template_name}' not found in {self._prompts_dir}"
            )

        content = path.read_text(encoding="utf-8")
        self._cache[template_name] = content
        return content

    def render(self, template_name: str, variables: dict[str, Any]) -> str:
        """Render a template with variable injection.

        Replaces {{variable_name}} placeholders with values from the
        variables dict. Logs MissingVariableWarning for undefined variables.

        Args:
            template_name: Template identifier.
            variables: Dict of variable names to values.

        Returns:
            Rendered prompt text.

        Warns:
            MissingVariableWarning: For each undefined variable.
        """
        template = self.load(template_name)
        return self._inject_variables(template, variables)

    def get_metadata(self, template_name: str) -> dict[str, Any]:
        """Get metadata for a prompt template.

        Metadata can be defined in the template file as YAML front-matter
        between --- delimiters at the top of the file.

        Args:
            template_name: Template identifier.

        Returns:
            Metadata dict (empty if no front-matter).
        """
        if template_name in self._metadata:
            return self._metadata[template_name]

        try:
            content = self.load(template_name)
            metadata = self._parse_frontmatter(content)
            self._metadata[template_name] = metadata
            return metadata
        except Exception:
            return {}

    def reload(self, template_name: str | None = None) -> None:
        """Reload template(s) from disk, clearing the cache.

        Args:
            template_name: Specific template to reload, or None for all.
        """
        if template_name:
            self._cache.pop(template_name, None)
            self._metadata.pop(template_name, None)
        else:
            self._cache.clear()
            self._metadata.clear()
            self._build_index()

    def list_templates(self) -> list[str]:
        """List all available template names.

        Returns:
            Sorted list of template identifiers.
        """
        return sorted(self._index.keys())

    # ============================================================
    # Private helpers
    # ============================================================

    @staticmethod
    def _inject_variables(template: str, variables: dict[str, Any]) -> str:
        """Inject variables into a template string.

        Replaces {{variable_name}} with the corresponding value.
        Undefined variables produce a warning and remain as-is.

        Args:
            template: Template text with {{variable}} placeholders.
            variables: Dict of variable names to values.

        Returns:
            Rendered text with variables substituted.
        """
        def _replacer(match: re.Match) -> str:
            var_name = match.group(1).strip()
            if var_name in variables:
                return str(variables[var_name])
            warnings.warn(
                f"MissingVariableWarning: template variable '{var_name}' "
                f"has no corresponding value",
                MissingVariableWarning,
                stacklevel=4,
            )
            return match.group(0)  # Leave placeholder as-is

        pattern = r"\{\{([^}]+)\}\}"
        return re.sub(pattern, _replacer, template)

    @staticmethod
    def _parse_frontmatter(content: str) -> dict[str, Any]:
        """Parse YAML front-matter from template content.

        Front-matter is delimited by --- at the start of the file:
        ---
        version: v1
        description: System prompt for all agents
        ---

        Args:
            content: Full template text.

        Returns:
            Parsed metadata dict.
        """
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        frontmatter = parts[1].strip()
        metadata: dict[str, Any] = {}

        for line in frontmatter.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                metadata[key.strip()] = value.strip()

        return metadata
