"""Unit tests for geospatial storage domain models.

Tests dataclass construction, default values, field types, and Shapely geometry handling.
No database connection required.
"""

from dataclasses import fields

import pytest

from src.geospatial.domain.models import (
    Alert,
    AuditLog,
    EconomicImpact,
    GeospatialProcessingJob,
    Indicator,
    ProcessedLayer,
    Region,
    RiskAssessment,
)


class TestRegionDataclass:
    """Test Region dataclass construction and defaults."""

    def test_minimal_construction(self):
        """Test Region can be created with only required field."""
        region = Region(name="Chaco")
        assert region.name == "Chaco"
        assert region.id is None
        assert region.geometry is None
        assert region.region_type == "administrative"
        assert region.country is None
        assert region.province is None
        assert region.bbox is None
        assert region.area_km2 is None
        assert region.metadata == {}
        assert region.is_active is True

    def test_full_construction(self):
        """Test Region with all fields populated."""
        region = Region(
            id=1,
            name="Chaco",
            region_type="province",
            country="Argentina",
            province="Chaco",
            bbox=[-62.0, -28.0, -58.0, -25.0],
            area_km2=99633.0,
            metadata={"source": "IGN"},
            is_active=True,
        )
        assert region.id == 1
        assert region.name == "Chaco"
        assert region.region_type == "province"
        assert region.country == "Argentina"
        assert region.bbox == [-62.0, -28.0, -58.0, -25.0]
        assert region.area_km2 == 99633.0
        assert region.metadata == {"source": "IGN"}

    def test_default_metadata_is_independent(self):
        """Test that default metadata dict is not shared between instances."""
        r1 = Region(name="A")
        r2 = Region(name="B")
        r1.metadata["key"] = "value"
        assert "key" not in r2.metadata


class TestIndicatorDataclass:
    """Test Indicator dataclass construction and defaults."""

    def test_minimal_construction(self):
        """Test Indicator with required fields only."""
        indicator = Indicator(region_id=1, indicator_code="SM_INDEX")
        assert indicator.region_id == 1
        assert indicator.indicator_code == "SM_INDEX"
        assert indicator.id is None
        assert indicator.processed_layer_id is None
        assert indicator.value is None
        assert indicator.metadata == {}

    def test_full_construction(self):
        """Test Indicator with all fields."""
        indicator = Indicator(
            id=1,
            region_id=5,
            indicator_code="NDVI",
            indicator_name="Normalized Difference Vegetation Index",
            indicator_type="vegetation",
            value=0.75,
            unit="index",
            classification="healthy",
            confidence=0.9,
            calculation_method="mean_pixel_value",
            temporal_start="2024-01-01",
            temporal_end="2024-01-31",
            processed_layer_id=10,
        )
        assert indicator.id == 1
        assert indicator.value == 0.75
        assert indicator.confidence == 0.9


class TestRiskAssessmentDataclass:
    """Test RiskAssessment dataclass construction and defaults."""

    def test_minimal_construction(self):
        """Test RiskAssessment with required fields only."""
        assessment = RiskAssessment(
            region_id=1, risk_type="drought", risk_level="high"
        )
        assert assessment.region_id == 1
        assert assessment.risk_type == "drought"
        assert assessment.risk_level == "high"
        assert assessment.id is None
        assert assessment.indicator_id is None
        assert assessment.risk_score is None
        assert assessment.metadata == {}

    def test_with_explanation(self):
        """Test RiskAssessment with explanation text."""
        assessment = RiskAssessment(
            region_id=1,
            risk_type="flood",
            risk_level="critical",
            risk_score=0.95,
            explanation="Severe flooding expected due to heavy rainfall",
            method="hydrological_model",
        )
        assert assessment.risk_score == 0.95
        assert "Severe flooding" in assessment.explanation


class TestAlertDataclass:
    """Test Alert dataclass construction and defaults."""

    def test_minimal_construction(self):
        """Test Alert with required fields only."""
        alert = Alert(
            region_id=1, alert_type="drought_warning", severity="warning", title="Drought Alert"
        )
        assert alert.region_id == 1
        assert alert.severity == "warning"
        assert alert.title == "Drought Alert"
        assert alert.status == "active"
        assert alert.id is None
        assert alert.message is None
        assert alert.metadata == {}

    def test_with_message_and_status(self):
        """Test Alert with message and resolved status."""
        alert = Alert(
            region_id=1,
            alert_type="flood",
            severity="critical",
            title="Flood Warning",
            message="River levels exceeding threshold",
            status="resolved",
            resolved_at="2024-03-15T10:00:00",
        )
        assert alert.status == "resolved"
        assert alert.resolved_at == "2024-03-15T10:00:00"


class TestEconomicImpactDataclass:
    """Test EconomicImpact dataclass construction and defaults."""

    def test_minimal_construction(self):
        """Test EconomicImpact with required fields only."""
        impact = EconomicImpact(region_id=1, impact_type="crop_loss")
        assert impact.region_id == 1
        assert impact.impact_type == "crop_loss"
        assert impact.id is None
        assert impact.estimated_loss_usd is None
        assert impact.metadata == {}

    def test_full_construction(self):
        """Test EconomicImpact with all fields."""
        impact = EconomicImpact(
            id=1,
            region_id=5,
            impact_type="crop_loss",
            estimated_loss_usd=1500000.0,
            affected_area_ha=5000.0,
            crop_type="soybean",
            yield_loss_percentage=25.0,
            method="statistical_model",
            assumptions="Based on SMAP soil moisture data",
            confidence=0.8,
        )
        assert impact.estimated_loss_usd == 1500000.0
        assert impact.crop_type == "soybean"
        assert impact.yield_loss_percentage == 25.0


class TestAuditLogDataclass:
    """Test AuditLog dataclass construction and defaults."""

    def test_minimal_construction(self):
        """Test AuditLog with required fields only."""
        log = AuditLog(entity_type="region", action="create")
        assert log.entity_type == "region"
        assert log.action == "create"
        assert log.actor_type == "system"
        assert log.id is None
        assert log.entity_id is None
        assert log.metadata == {}

    def test_with_actor_and_message(self):
        """Test AuditLog with explicit actor and message."""
        log = AuditLog(
            entity_type="indicator",
            entity_id="42",
            action="complete",
            actor_type="agent",
            actor_id="pipeline-001",
            message="Indicator calculation completed successfully",
        )
        assert log.actor_type == "agent"
        assert log.actor_id == "pipeline-001"
        assert "completed" in log.message


class TestProcessedLayerExtended:
    """Test ProcessedLayer with new M3 fields."""

    def test_original_fields_unchanged(self):
        """Test that original ProcessedLayer fields still work."""
        layer = ProcessedLayer(
            raw_file_id=1,
            processing_job_id="job-123",
            source_code="SMAP",
            variable_name="sm_surface",
            file_path="/data/test.tif",
            crs="EPSG:6933",
            bbox=[-17367530.0, 7269540.0, -17277530.0, 7314540.0],
            resolution_x=9000.0,
            resolution_y=9000.0,
            width=10,
            height=5,
            nodata_value=-9999.0,
            min_value=0.0,
            max_value=0.6,
            mean_value=0.3,
            valid_pixel_count=48,
            nodata_pixel_count=2,
            acquisition_date="2023-12-31",
            processing_version="v1",
        )
        assert layer.id is None
        assert layer.footprint_geometry is None
        assert layer.data_source_id is None
        assert layer.data_source_code is None

    def test_new_fields_can_be_set(self):
        """Test that new M3 fields can be populated."""
        layer = ProcessedLayer(
            raw_file_id=1,
            processing_job_id="job-123",
            source_code="SMAP",
            variable_name="sm_surface",
            file_path="/data/test.tif",
            crs="EPSG:6933",
            bbox=[-17367530.0, 7269540.0, -17277530.0, 7314540.0],
            resolution_x=9000.0,
            resolution_y=9000.0,
            width=10,
            height=5,
            nodata_value=-9999.0,
            min_value=0.0,
            max_value=0.6,
            mean_value=0.3,
            valid_pixel_count=48,
            nodata_pixel_count=2,
            acquisition_date="2023-12-31",
            processing_version="v1",
            data_source_id=1,
            data_source_code="SMAP_L3",
        )
        assert layer.data_source_id == 1
        assert layer.data_source_code == "SMAP_L3"
        assert layer.footprint_geometry is None


class TestGeospatialProcessingJobUnchanged:
    """Verify GeospatialProcessingJob is not affected by M3 additions."""

    def test_construction_unchanged(self):
        """Test GeospatialProcessingJob still works as before."""
        job = GeospatialProcessingJob(
            id="job-123",
            raw_file_id=1,
            source_code="SMAP",
            status="pending",
        )
        assert job.id == "job-123"
        assert job.status == "pending"
        assert job.warnings == []
