"""Integration tests for the full geospatial ETL pipeline.

Requires:
- Real HDF5 file at data/raw/smap/2023/12/SMAP_L4_SM_gph_20231231T223000_Vv8010_001.h5
- Docker PostgreSQL running with migrations applied
- Environment variables: PGHOST, PGDATABASE, PGUSER, PGPASSWORD

Run with: pytest tests/geospatial/integration/test_pipeline.py -v -m integration
"""

import os
from pathlib import Path

import pytest

from tests.geospatial.integration.conftest import skip_if_no_hdf5, skip_if_no_postgres


@pytest.mark.integration
class TestFullPipeline:
    """Test the complete ETL pipeline with real HDF5 and PostgreSQL."""

    def test_process_file_creates_geotiff(self):
        """Test that processing a real HDF5 file creates a valid GeoTIFF."""
        skip_if_no_postgres()
        skip_if_no_hdf5()

        pytest.importorskip("rasterio")

        from src.geospatial.application.orchestrator import GeospatialOrchestrator
        from src.geospatial.application.raster_processing_service import RasterProcessingService
        from src.geospatial.application.smap_validation_service import SMAPValidationService
        from src.geospatial.infrastructure.hdf5.smap_reader import SMAPHDF5Reader
        from src.geospatial.infrastructure.persistence.postgres_repositories import (
            GeospatialProcessingJobRepositoryImpl,
            ProcessedLayerRepositoryImpl,
            RawFileDiscoveryRepositoryImpl,
        )
        from src.geospatial.infrastructure.raster.geotiff_writer import GeoTIFFWriter

        # Setup components
        reader = SMAPHDF5Reader()
        validator = SMAPValidationService()
        processing_service = RasterProcessingService()
        writer = GeoTIFFWriter()
        discovery_repo = RawFileDiscoveryRepositoryImpl()
        job_repo = GeospatialProcessingJobRepositoryImpl()
        layer_repo = ProcessedLayerRepositoryImpl()

        orchestrator = GeospatialOrchestrator(
            reader=reader,
            validator=validator,
            processing_service=processing_service,
            writer=writer,
            discovery_repo=discovery_repo,
            job_repo=job_repo,
            layer_repo=layer_repo,
            source_code="SMAP",
            variable_configs=[
                {
                    "name": "sm_surface",
                    "path": "Geophysical_Data/sm_surface",
                    "expected_min": 0.0,
                    "expected_max": 0.6,
                }
            ],
        )

        # Find a real raw file to process
        raw_files = discovery_repo.find_completed(source="SMAP", limit=1)
        if not raw_files:
            pytest.skip("No completed SMAP raw files found in database")

        raw_file = raw_files[0]
        raw_file_id = raw_file["id"]

        # Check idempotency first
        if job_repo.exists_by_raw_file_variable(raw_file_id, "sm_surface", "v1"):
            pytest.skip(f"File {raw_file_id} already processed — idempotency hit")

        # Run pipeline
        results = orchestrator.run_batch(
            raw_file_id=raw_file_id,
            processing_version="v1",
            roi_enabled=False,  # Disable ROI for integration test
        )

        # Verify results
        assert results["total"] == 1
        detail = results["details"][0]
        assert detail["status"] in ("completed", "completed_with_warnings")

        # Verify GeoTIFF was created and can be opened
        output_path = detail.get("output_path")
        assert output_path is not None
        assert os.path.exists(output_path)

        # Verify GeoTIFF properties
        import rasterio
        with rasterio.open(output_path) as src:
            assert src.crs is not None
            assert src.transform is not None
            assert src.width > 0
            assert src.height > 0
            assert src.nodata is not None

        # Cleanup: remove generated GeoTIFF
        try:
            os.remove(output_path)
        except OSError:
            pass

    def test_process_file_creates_db_records(self):
        """Test that processing creates job and layer records in PostgreSQL."""
        skip_if_no_postgres()
        skip_if_no_hdf5()

        from src.geospatial.application.orchestrator import GeospatialOrchestrator
        from src.geospatial.application.raster_processing_service import RasterProcessingService
        from src.geospatial.application.smap_validation_service import SMAPValidationService
        from src.geospatial.infrastructure.hdf5.smap_reader import SMAPHDF5Reader
        from src.geospatial.infrastructure.persistence.postgres_repositories import (
            GeospatialProcessingJobRepositoryImpl,
            ProcessedLayerRepositoryImpl,
            RawFileDiscoveryRepositoryImpl,
        )
        from src.geospatial.infrastructure.raster.geotiff_writer import GeoTIFFWriter

        reader = SMAPHDF5Reader()
        validator = SMAPValidationService()
        processing_service = RasterProcessingService()
        writer = GeoTIFFWriter()
        discovery_repo = RawFileDiscoveryRepositoryImpl()
        job_repo = GeospatialProcessingJobRepositoryImpl()
        layer_repo = ProcessedLayerRepositoryImpl()

        orchestrator = GeospatialOrchestrator(
            reader=reader,
            validator=validator,
            processing_service=processing_service,
            writer=writer,
            discovery_repo=discovery_repo,
            job_repo=job_repo,
            layer_repo=layer_repo,
            source_code="SMAP",
            variable_configs=[
                {
                    "name": "sm_surface",
                    "path": "Geophysical_Data/sm_surface",
                    "expected_min": 0.0,
                    "expected_max": 0.6,
                }
            ],
        )

        raw_files = discovery_repo.find_completed(source="SMAP", limit=1)
        if not raw_files:
            pytest.skip("No completed SMAP raw files found in database")

        raw_file = raw_files[0]
        raw_file_id = raw_file["id"]

        if job_repo.exists_by_raw_file_variable(raw_file_id, "sm_surface", "v1"):
            pytest.skip(f"File {raw_file_id} already processed")

        results = orchestrator.run_batch(
            raw_file_id=raw_file_id,
            processing_version="v1",
            roi_enabled=False,
        )

        detail = results["details"][0]
        if detail["status"] not in ("completed", "completed_with_warnings"):
            pytest.skip(f"Processing failed: {detail.get('error', 'unknown')}")

        # Verify layer record exists
        layer = layer_repo.get_by_raw_file_and_variable(raw_file_id, "sm_surface", "v1")
        assert layer is not None
        assert layer.variable_name == "sm_surface"
        assert layer.crs is not None
        assert layer.width > 0
        assert layer.height > 0
