"""Domain constants for the AI ecosystem (Módulo 4).

M4 owns its constants — does NOT import from M3. Values may overlap with M3
enums (e.g. AiActorType.SYSTEM matches ActorType.SYSTEM) but the source of
truth is independent to avoid cross-module coupling.
"""

from enum import Enum


class WorkflowStatus(str, Enum):
    """Lifecycle states for AI workflows."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AiActorType(str, Enum):
    """Types of actors that perform AI actions.

    Mirrors M3's ActorType values by copy, not by import.
    M4 can evolve independently.
    """

    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"
    REFERENCE_AGENT = "reference_agent"


class ToolType(str, Enum):
    """Categories of tools available to AI agents."""

    GEOSPATIAL_QUERY = "geospatial_query"
    INDICATOR_LOOKUP = "indicator_lookup"
    RISK_ASSESSMENT = "risk_assessment"
    SUMMARIZATION = "summarization"
    STRUCTURED_OUTPUT = "structured_output"
