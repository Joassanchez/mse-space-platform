"""Domain constants for the geospatial storage layer.

Enums define the allowed values for risk types, alert severities, entity types,
and other categorical fields used across the geospatial storage domain.
"""

from enum import Enum


class EntityType(str, Enum):
    """Types of entities tracked in audit logs and domain operations."""

    REGION = "region"
    INDICATOR = "indicator"
    RISK_ASSESSMENT = "risk_assessment"
    ALERT = "alert"
    ECONOMIC_IMPACT = "economic_impact"
    PROCESSED_LAYER = "processed_layer"
    PIPELINE_BATCH = "pipeline_batch"
    AUDIT_LOG = "audit_log"


class Action(str, Enum):
    """Actions performed on domain entities."""

    START = "start"
    COMPLETE = "complete"
    FAIL = "fail"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class ActorType(str, Enum):
    """Types of actors that perform actions."""

    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"


class RiskType(str, Enum):
    """Types of risk assessments."""

    DROUGHT = "drought"
    FLOOD = "flood"
    HYDRIC_STRESS = "hydric_stress"
    AGROENVIRONMENTAL = "agroenvironmental"


class RiskLevel(str, Enum):
    """Risk severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Severity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    SEVERE = "severe"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Lifecycle states for alerts."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class RegionType(str, Enum):
    """Classification of geographic regions."""

    ADMINISTRATIVE = "administrative"
    PROVINCE = "province"
    MUNICIPALITY = "municipality"
    DEPARTMENT = "department"
    WATER_BASIN = "water_basin"
    PILOT_LOT = "pilot_lot"
    TEST_REGION = "test_region"
    USER_DEFINED = "user_defined"
