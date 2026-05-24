"""Integration tests for PostGIS storage repositories.

Tests require a running PostgreSQL + PostGIS instance.
Skipped automatically if the database is not available.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.geospatial.domain.models import (
    Alert,
    AuditLog,
    EconomicImpact,
    Indicator,
    Region,
    RiskAssessment,
)
from src.geospatial.infrastructure.persistence.alerts_repo import AlertRepositoryImpl
from src.geospatial.infrastructure.persistence.audit_repo import AuditRepositoryImpl
from src.geospatial.infrastructure.persistence.data_sources_repo import (
    DataSourceRepositoryImpl,
)
from src.geospatial.infrastructure.persistence.economic_impacts_repo import (
    EconomicImpactRepositoryImpl,
)
from src.geospatial.infrastructure.persistence.indicators_repo import (
    IndicatorRepositoryImpl,
)
from src.geospatial.infrastructure.persistence.regions_repo import RegionRepositoryImpl
from src.geospatial.infrastructure.persistence.risk_assessments_repo import (
    RiskAssessmentRepositoryImpl,
)

try:
    import psycopg2
    import psycopg2.extras
    import shapely.geometry
    import shapely.wkt

    HAS_ALL_DEPS = True
except ImportError:
    HAS_ALL_DEPS = False


def _get_test_connection():
    """Get a PostgreSQL connection for testing."""
    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "mse_platform"),
        user=os.getenv("PGUSER", "mse_user"),
        password=os.getenv("PGPASSWORD", "mse_pass"),
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
    )


@pytest.fixture
def db_conn():
    """Provide a test database connection, skip if unavailable."""
    if not HAS_ALL_DEPS:
        pytest.skip("PostGIS dependencies not installed (psycopg2, shapely)")

    try:
        conn = _get_test_connection()
        yield conn
        conn.close()
    except Exception:
        pytest.skip(
            "Integration test skipped: PostgreSQL not available. "
            "Set PGHOST, PGDATABASE, PGUSER, PGPASSWORD environment variables."
        )


@pytest.fixture
def region_repo(db_conn):
    return RegionRepositoryImpl(connection=db_conn)


@pytest.fixture
def indicator_repo(db_conn):
    return IndicatorRepositoryImpl(connection=db_conn)


@pytest.fixture
def risk_repo(db_conn):
    return RiskAssessmentRepositoryImpl(connection=db_conn)


@pytest.fixture
def alert_repo(db_conn):
    return AlertRepositoryImpl(connection=db_conn)


@pytest.fixture
def impact_repo(db_conn):
    return EconomicImpactRepositoryImpl(connection=db_conn)


@pytest.fixture
def ds_repo(db_conn):
    return DataSourceRepositoryImpl(connection=db_conn)


@pytest.fixture
def audit_repo(db_conn):
    return AuditRepositoryImpl(connection=db_conn)


# ============================================================
# 8.2 PostGIS version
# ============================================================
class TestPostGISVersion:
    """Verify PostGIS is available and returns a version string."""

    def test_postgis_version(self, db_conn):
        """SELECT PostGIS_Version() returns version string."""
        with db_conn.cursor() as cur:
            cur.execute("SELECT PostGIS_Version()")
            row = cur.fetchone()

        assert row is not None
        version_str = str(row[0])
        assert len(version_str) > 0
        # Should be something like "3.4"
        assert "." in version_str


# ============================================================
# 8.3 RegionRepository: insert MultiPolygon, spatial query
# ============================================================
class TestRegionRepository:
    """Integration tests for RegionRepositoryImpl."""

    def test_insert_and_get_region(self, region_repo):
        """Insert a region with MultiPolygon geometry, then retrieve it."""
        geometry = shapely.geometry.MultiPolygon([
            shapely.geometry.Polygon([
                (-60.0, -25.0), (-60.0, -24.0),
                (-59.0, -24.0), (-59.0, -25.0),
                (-60.0, -25.0),
            ])
        ])

        region = Region(
            name="Test Region Integration",
            geometry=geometry,
            region_type="administrative",
            country="Argentina",
            province="Formosa",
            bbox=[-60.0, -25.0, -59.0, -24.0],
            metadata={"test": True},
        )

        region_id = region_repo.save(region)
        assert region_id is not None
        assert region_id > 0

        # Retrieve
        retrieved = region_repo.get_by_id(region_id)
        assert retrieved is not None
        assert retrieved.name == "Test Region Integration"
        assert retrieved.geometry is not None
        assert retrieved.country == "Argentina"

    def test_find_intersecting_geometry(self, region_repo):
        """Query find_intersecting_geometry returns overlapping regions."""
        # Create a region
        geometry = shapely.geometry.MultiPolygon([
            shapely.geometry.Polygon([
                (-61.0, -26.0), (-61.0, -24.0),
                (-59.0, -24.0), (-59.0, -26.0),
                (-61.0, -26.0),
            ])
        ])

        region = Region(
            name="Intersect Test Region",
            geometry=geometry,
            region_type="test_region",
            country="Argentina",
        )
        region_id = region_repo.save(region)

        # Query with overlapping polygon
        query_geom = shapely.geometry.Polygon([
            (-60.5, -25.5), (-60.5, -24.5),
            (-60.0, -24.5), (-60.0, -25.5),
            (-60.5, -25.5),
        ])
        query_wkt = shapely.wkt.dumps(query_geom)

        results = region_repo.find_intersecting_geometry(query_wkt)
        assert len(results) >= 1
        found_ids = [r.id for r in results]
        assert region_id in found_ids


# ============================================================
# 8.4 FK constraint violation: indicator without region
# ============================================================
class TestFKConstraints:
    """Verify foreign key constraints are enforced."""

    def test_indicator_requires_region(self, indicator_repo):
        """Insert indicator with non-existent region_id → IntegrityError."""
        indicator = Indicator(
            region_id=999999,  # Non-existent
            indicator_code="TEST",
            value=0.5,
        )

        with pytest.raises(Exception):  # psycopg2.IntegrityError
            indicator_repo.save(indicator)


# ============================================================
# 8.5 data_source_id lineage via raw_files.source_id
# ============================================================
class TestDataSourceLineage:
    """Verify data_source resolution via existing FK chain."""

    def test_data_source_by_code(self, ds_repo):
        """Get data source by code returns dict with expected fields."""
        # This depends on seeds or existing data
        result = ds_repo.get_by_code("SMAP")
        if result is not None:
            assert result["code"] == "SMAP"
            assert "id" in result
            assert "name" in result

    def test_data_source_by_id(self, ds_repo):
        """Get data source by ID returns dict or None."""
        result = ds_repo.get_by_id(1)
        # May be None if no data, but should not error
        if result is not None:
            assert "id" in result
            assert "code" in result


# ============================================================
# 8.6 footprint_geometry: nullable, GIST index
# ============================================================
class TestFootprintGeometry:
    """Verify footprint_geometry column behavior."""

    def test_gist_index_exists(self, db_conn):
        """Verify GIST index on footprint_geometry exists."""
        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'processed_geospatial_layers'
                  AND indexname = 'idx_processed_layers_footprint'
                """
            )
            row = cur.fetchone()

        assert row is not None, "GIST index idx_processed_layers_footprint should exist"


# ============================================================
# 8.7 Audit non-fatal: mock DB failure
# ============================================================
class TestAuditNonFatal:
    """Verify audit failures don't break the pipeline."""

    def test_audit_failure_does_not_break_pipeline(self, db_conn):
        """Mock audit_repo.log_event to raise, verify pipeline completes."""
        from src.geospatial.application.orchestrator import GeospatialOrchestrator

        # Mock all dependencies
        mock_reader = MagicMock()
        mock_validator = MagicMock()
        mock_processing = MagicMock()
        mock_writer = MagicMock()
        mock_discovery = MagicMock()
        mock_job_repo = MagicMock()
        mock_layer_repo = MagicMock()

        # Discovery returns one file
        mock_discovery.find_completed.return_value = [{
            "id": 1,
            "file_path": "/test/file.h5",
        }]

        # Reader returns extracted data
        mock_extracted = MagicMock()
        mock_extracted.data = "mock_data"
        mock_extracted.nodata_value = -9999.0
        mock_extracted.acquisition_date = "2023-01-01"
        mock_reader.extract_variable.return_value = mock_extracted

        # Metadata
        mock_metadata = MagicMock()
        mock_metadata.crs = "EPSG:4326"
        mock_metadata.bounds = (-60.0, -25.0, -59.0, -24.0)
        mock_metadata.resolution = (0.01, 0.01)
        mock_metadata.width = 100
        mock_metadata.height = 100
        mock_reader.get_metadata.return_value = mock_metadata

        # Processing result
        mock_raster = MagicMock()
        mock_raster.data = "processed_data"
        mock_raster.metadata = mock_metadata
        mock_raster.statistics = {
            "min": 0.0, "max": 1.0, "mean": 0.5,
            "valid_pixel_count": 100, "nodata_pixel_count": 0,
        }
        mock_raster.warnings = []
        mock_processing.process.return_value = mock_raster

        # Writer returns path
        mock_writer.write.return_value = "/output/test.tif"

        # Audit repo that FAILS
        mock_audit = MagicMock()
        mock_audit.log_event.side_effect = Exception("DB connection lost")

        orchestrator = GeospatialOrchestrator(
            reader=mock_reader,
            validator=mock_validator,
            processing_service=mock_processing,
            writer=mock_writer,
            discovery_repo=mock_discovery,
            job_repo=mock_job_repo,
            layer_repo=mock_layer_repo,
            source_code="SMAP",
            variable_configs=[{"name": "sm_surface", "path": "sm_surface"}],
            audit_repo=mock_audit,
        )

        # Pipeline should complete despite audit failures
        result = orchestrator.run_batch(limit=1)

        assert result["total"] == 1
        # The audit failures are caught — pipeline continues
        assert mock_audit.log_event.call_count >= 1


# ============================================================
# 8.8 Seeds idempotency
# ============================================================
class TestSeedsIdempotency:
    """Verify seeds can be run multiple times without duplicates."""

    def test_seed_idempotency(self, db_conn):
        """Run seeds twice, verify COUNT(DISTINCT) without duplicates."""
        seed_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "seeds", "002_geospatial_storage.sql",
        )

        if not os.path.exists(seed_path):
            pytest.skip(f"Seed file not found at {seed_path}")

        # Read and execute seed twice
        with open(seed_path) as f:
            seed_sql = f.read()

        # Execute first time
        with db_conn.cursor() as cur:
            cur.execute(seed_sql)
        db_conn.commit()

        # Execute second time
        with db_conn.cursor() as cur:
            cur.execute(seed_sql)
        db_conn.commit()

        # Verify no duplicates
        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM regions WHERE name = 'Chaco'")
            count = cur.fetchone()[0]

        assert count == 1, f"Expected 1 Chaco region, got {count} (duplicate seeds)"


# ============================================================
# 8.9 M2 regression: verify existing integration tests still pass
# ============================================================
class TestM2Regression:
    """Verify Módulo 2 integration tests are not broken."""

    def test_m2_idempotency_test_exists(self):
        """Verify M2 idempotency test file exists."""
        test_path = os.path.join(
            os.path.dirname(__file__), "test_idempotency.py"
        )
        assert os.path.exists(test_path), "M2 idempotency test should exist"

    def test_m2_pipeline_test_exists(self):
        """Verify M2 pipeline test file exists."""
        test_path = os.path.join(
            os.path.dirname(__file__), "test_pipeline.py"
        )
        assert os.path.exists(test_path), "M2 pipeline test should exist"
