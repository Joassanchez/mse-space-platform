"""Unit tests for geospatial domain constants (enums).

Validates all enum members, string values, and uniqueness.
"""

import pytest

from src.geospatial.domain.constants import (
    Action,
    ActorType,
    AlertStatus,
    EntityType,
    RegionType,
    RiskLevel,
    RiskType,
    Severity,
)


class TestEntityType:
    """Test EntityType enum."""

    def test_all_members_exist(self):
        """Verify all expected members are present."""
        expected = [
            "REGION", "INDICATOR", "RISK_ASSESSMENT", "ALERT",
            "ECONOMIC_IMPACT", "PROCESSED_LAYER", "PIPELINE_BATCH", "AUDIT_LOG",
        ]
        for name in expected:
            assert hasattr(EntityType, name), f"Missing EntityType.{name}"

    def test_string_values(self):
        """Verify string values match member names (lowercase)."""
        assert EntityType.REGION.value == "region"
        assert EntityType.INDICATOR.value == "indicator"
        assert EntityType.RISK_ASSESSMENT.value == "risk_assessment"
        assert EntityType.ALERT.value == "alert"
        assert EntityType.ECONOMIC_IMPACT.value == "economic_impact"
        assert EntityType.PROCESSED_LAYER.value == "processed_layer"
        assert EntityType.PIPELINE_BATCH.value == "pipeline_batch"
        assert EntityType.AUDIT_LOG.value == "audit_log"

    def test_uniqueness(self):
        """Verify all values are unique."""
        values = [e.value for e in EntityType]
        assert len(values) == len(set(values))


class TestAction:
    """Test Action enum."""

    def test_all_members_exist(self):
        expected = ["START", "COMPLETE", "FAIL", "CREATE", "UPDATE", "DELETE"]
        for name in expected:
            assert hasattr(Action, name), f"Missing Action.{name}"

    def test_string_values(self):
        assert Action.START.value == "start"
        assert Action.COMPLETE.value == "complete"
        assert Action.FAIL.value == "fail"
        assert Action.CREATE.value == "create"
        assert Action.UPDATE.value == "update"
        assert Action.DELETE.value == "delete"

    def test_uniqueness(self):
        values = [e.value for e in Action]
        assert len(values) == len(set(values))


class TestActorType:
    """Test ActorType enum."""

    def test_all_members_exist(self):
        for name in ["SYSTEM", "USER", "AGENT"]:
            assert hasattr(ActorType, name), f"Missing ActorType.{name}"

    def test_string_values(self):
        assert ActorType.SYSTEM.value == "system"
        assert ActorType.USER.value == "user"
        assert ActorType.AGENT.value == "agent"

    def test_uniqueness(self):
        values = [e.value for e in ActorType]
        assert len(values) == len(set(values))


class TestRiskType:
    """Test RiskType enum."""

    def test_all_members_exist(self):
        for name in ["DROUGHT", "FLOOD", "HYDRIC_STRESS", "AGROENVIRONMENTAL"]:
            assert hasattr(RiskType, name), f"Missing RiskType.{name}"

    def test_string_values(self):
        assert RiskType.DROUGHT.value == "drought"
        assert RiskType.FLOOD.value == "flood"
        assert RiskType.HYDRIC_STRESS.value == "hydric_stress"
        assert RiskType.AGROENVIRONMENTAL.value == "agroenvironmental"

    def test_uniqueness(self):
        values = [e.value for e in RiskType]
        assert len(values) == len(set(values))


class TestRiskLevel:
    """Test RiskLevel enum."""

    def test_all_members_exist(self):
        for name in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            assert hasattr(RiskLevel, name), f"Missing RiskLevel.{name}"

    def test_string_values(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_uniqueness(self):
        values = [e.value for e in RiskLevel]
        assert len(values) == len(set(values))


class TestSeverity:
    """Test Severity enum."""

    def test_all_members_exist(self):
        for name in ["INFO", "WARNING", "SEVERE", "CRITICAL"]:
            assert hasattr(Severity, name), f"Missing Severity.{name}"

    def test_string_values(self):
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.SEVERE.value == "severe"
        assert Severity.CRITICAL.value == "critical"

    def test_uniqueness(self):
        values = [e.value for e in Severity]
        assert len(values) == len(set(values))


class TestAlertStatus:
    """Test AlertStatus enum."""

    def test_all_members_exist(self):
        for name in ["ACTIVE", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"]:
            assert hasattr(AlertStatus, name), f"Missing AlertStatus.{name}"

    def test_string_values(self):
        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.DISMISSED.value == "dismissed"

    def test_uniqueness(self):
        values = [e.value for e in AlertStatus]
        assert len(values) == len(set(values))


class TestRegionType:
    """Test RegionType enum."""

    def test_all_members_exist(self):
        expected = [
            "ADMINISTRATIVE", "PROVINCE", "MUNICIPALITY", "DEPARTMENT",
            "WATER_BASIN", "PILOT_LOT", "TEST_REGION", "USER_DEFINED",
        ]
        for name in expected:
            assert hasattr(RegionType, name), f"Missing RegionType.{name}"

    def test_string_values(self):
        assert RegionType.ADMINISTRATIVE.value == "administrative"
        assert RegionType.PROVINCE.value == "province"
        assert RegionType.MUNICIPALITY.value == "municipality"
        assert RegionType.DEPARTMENT.value == "department"
        assert RegionType.WATER_BASIN.value == "water_basin"
        assert RegionType.PILOT_LOT.value == "pilot_lot"
        assert RegionType.TEST_REGION.value == "test_region"
        assert RegionType.USER_DEFINED.value == "user_defined"

    def test_uniqueness(self):
        values = [e.value for e in RegionType]
        assert len(values) == len(set(values))
