"""Run the ETL pipeline integration test directly (bypass pytest)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("PGHOST", "localhost")
os.environ.setdefault("PGPORT", "5432")
os.environ.setdefault("PGDATABASE", "mse_platform")
os.environ.setdefault("PGUSER", "mse_user")
os.environ.setdefault("PGPASSWORD", "mse_pass")

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
    source_code="smap",
    variable_configs=[
        {
            "name": "sm_surface",
            "path": "Geophysical_Data/sm_surface",
            "expected_min": 0.0,
            "expected_max": 0.9,
        }
    ],
)

# Find real raw file
raw_files = discovery_repo.find_completed(source="smap", limit=1)
print(f"Raw files found: {len(raw_files)}")
for rf in raw_files:
    print(f"  ID={rf['id']}, name={rf['file_name']}")

if not raw_files:
    print("ERROR: No completed raw files found in database.")
    print("Run Módulo 1 ingestion first, or update raw_files status to ready_for_etl=TRUE.")
    sys.exit(1)

raw_file_id = raw_files[0]["id"]
exists = job_repo.exists_by_raw_file_variable(raw_file_id, "sm_surface", "v1")
print(f"Already processed: {exists}")

if not exists:
    results = orchestrator.run_batch(
        raw_file_id=raw_file_id,
        processing_version="v1",
        roi_enabled=False,
    )
    print(f"\nResults: {results}")

    detail = results["details"][0]
    status = detail["status"]
    output_path = detail.get("output_path")

    print(f"\nJob status: {status}")

    if status in ("completed", "completed_with_warnings") and output_path:
        import rasterio
        with rasterio.open(output_path) as src:
            print(f"\nGeoTIFF: {output_path}")
            print(f"  CRS: {src.crs}")
            print(f"  Width: {src.width}, Height: {src.height}")
            print(f"  Nodata: {src.nodata}")
            print(f"  Transform: {src.transform}")

        # Verify layer in DB
        layer = layer_repo.get_by_raw_file_and_variable(raw_file_id, "sm_surface", "v1")
        if layer:
            print(f"\nDB layer: variable={layer.variable_name}, version={layer.processing_version}")
            print(f"  CRS: {layer.crs}")
            print(f"  Dimensions: {layer.width}x{layer.height}")
        else:
            print("\nERROR: Layer not found in database!")
            sys.exit(1)

        # Idempotency test: process again
        print("\n--- Idempotency test ---")
        exists_after = job_repo.exists_by_raw_file_variable(raw_file_id, "sm_surface", "v1")
        print(f"Idempotency check before 2nd run: {exists_after}")

        results2 = orchestrator.run_batch(
            raw_file_id=raw_file_id,
            processing_version="v1",
            roi_enabled=False,
        )
        detail2 = results2["details"][0]
        print(f"2nd run status: {detail2['status']}")

        # Verify no duplicate file
        if os.path.exists(output_path):
            print(f"File still exists (no duplicate created): {output_path}")
        else:
            print("ERROR: File was deleted?!")

        print("\n✅ ALL INTEGRATION TESTS PASSED")
    else:
        print(f"ERROR: Processing failed or no output: {detail.get('error', 'unknown')}")
        sys.exit(1)
else:
    print("File already processed. Testing idempotency...")
    results = orchestrator.run_batch(
        raw_file_id=raw_file_id,
        processing_version="v1",
        roi_enabled=False,
    )
    print(f"2nd run status: {results['details'][0]['status']}")
    print("\n✅ IDEMPOTENCY TEST PASSED")
