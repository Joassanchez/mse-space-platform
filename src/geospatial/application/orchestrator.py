"""Geospatial ETL orchestrator.

Coordinates the complete pipeline: discovery → idempotency check → create job →
read → validate → process raster → write GeoTIFF (tmp → atomic move) → persist
layer → finalize job.

Uses ports/interfaces (dependency injection), NOT concrete implementations.
Handles errors per file without breaking batch processing.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.geospatial.domain.errors import IdempotencySkip, ReadError, ValidationError, WriteError
from src.geospatial.domain.interfaces import (
    GeospatialProcessingJobRepository,
    GeospatialReader,
    GeospatialValidator,
    ProcessedLayerRepository,
    RawFileDiscoveryRepository,
)
from src.geospatial.domain.models import (
    GeospatialMetadata,
    GeospatialProcessingJob,
    ProcessedLayer,
)


class GeospatialOrchestrator:
    """Coordinates the geospatial ETL pipeline for a batch of raw files.

    All dependencies are injected via interfaces (ports). The orchestrator
    does not know about concrete implementations (SMAPHDF5Reader, etc.).

    Args:
        reader: GeospatialReader implementation for reading source files.
        validator: GeospatialValidator implementation for validating files.
        processing_service: Service for raster processing (nodata, ROI, stats).
        writer: GeoTIFFWriter implementation for writing output files.
        discovery_repo: Repository for discovering raw files pending processing.
        job_repo: Repository for CRUD on processing jobs.
        layer_repo: Repository for CRUD on processed layers.
        source_code: Source identifier (e.g. "SMAP").
        variable_configs: List of variable configs from sources.yaml.
    """

    def __init__(
        self,
        reader: GeospatialReader,
        validator: GeospatialValidator,
        processing_service: Any,  # RasterProcessingService
        writer: Any,  # GeoTIFFWriter
        discovery_repo: RawFileDiscoveryRepository,
        job_repo: GeospatialProcessingJobRepository,
        layer_repo: ProcessedLayerRepository,
        source_code: str,
        variable_configs: list[dict[str, Any]],
    ) -> None:
        self._reader = reader
        self._validator = validator
        self._processing_service = processing_service
        self._writer = writer
        self._discovery_repo = discovery_repo
        self._job_repo = job_repo
        self._layer_repo = layer_repo
        self._source_code = source_code
        self._variable_configs = variable_configs

    def run_batch(
        self,
        limit: int | None = None,
        raw_file_id: int | None = None,
        processing_version: str = "v1",
        roi_enabled: bool = True,
        roi_path: str | None = None,
    ) -> dict[str, Any]:
        """Run the ETL pipeline for a batch of raw files.

        Args:
            limit: Maximum number of files to process (None for all).
            raw_file_id: Process a specific raw file by ID.
            processing_version: Version string for processing (e.g. "v1").
            roi_enabled: Whether to apply ROI clipping.
            roi_path: Path to ROI GeoJSON file.

        Returns:
            Dict with summary: total, completed, skipped, failed, warnings.
        """
        # Discover files
        if raw_file_id is not None:
            raw_file = self._discovery_repo.find_by_id(raw_file_id)
            raw_files = [raw_file] if raw_file else []
        else:
            raw_files = self._discovery_repo.find_completed(
                source=self._source_code, limit=limit
            )

        if not raw_files:
            return {
                "total": 0,
                "completed": 0,
                "completed_with_warnings": 0,
                "skipped": 0,
                "failed": 0,
                "message": "No files to process",
            }

        # Build processing config
        processing_config = self._build_processing_config(
            roi_enabled, roi_path
        )

        results = {
            "total": len(raw_files),
            "completed": 0,
            "completed_with_warnings": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

        for raw_file in raw_files:
            file_result = self._process_single_file(
                raw_file=raw_file,
                processing_version=processing_version,
                processing_config=processing_config,
            )
            results["details"].append(file_result)

            status = file_result["status"]
            if status == "completed":
                results["completed"] += 1
            elif status == "completed_with_warnings":
                results["completed_with_warnings"] += 1
            elif status == "skipped":
                results["skipped"] += 1
            elif status == "failed":
                results["failed"] += 1

        return results

    def _process_single_file(
        self,
        raw_file: dict[str, Any],
        processing_version: str,
        processing_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Process a single raw file through the full ETL pipeline.

        Args:
            raw_file: Raw file dict from discovery repository.
            processing_version: Version string for processing.
            processing_config: Processing configuration (ROI, etc.).

        Returns:
            Dict with status, job_id, and optional error/message.
        """
        raw_file_id = raw_file["id"]
        file_path = Path(raw_file.get("file_path", ""))
        variable_config = self._variable_configs[0] if self._variable_configs else {}
        variable_name = variable_config.get("name", "sm_surface")
        variable_path = variable_config.get("path", "Geophysical_Data/sm_surface")

        # Step 1: Idempotency check
        if self._job_repo.exists_by_raw_file_variable(
            raw_file_id, variable_name, processing_version
        ):
            return {
                "raw_file_id": raw_file_id,
                "status": "skipped",
                "message": f"Idempotency hit: {variable_name} already processed for {raw_file_id}",
            }

        # Step 2: Create job (pending → running)
        job_id = str(uuid.uuid4())
        job = GeospatialProcessingJob(
            id=job_id,
            raw_file_id=raw_file_id,
            source_code=self._source_code,
            status="pending",
            created_at=datetime.now().isoformat(),
        )
        self._job_repo.create(job)
        self._job_repo.update_status(job_id, "running")

        try:
            # Step 3: Read HDF5
            self._reader.open(file_path)
            try:
                extracted = self._reader.extract_variable(variable_path)
                metadata = self._reader.get_metadata()
            finally:
                self._reader.close()

            # Step 4: Validate structure
            self._validator.validate_structure(file_path, variable_config)

            # Step 5: Validate variable
            self._validator.validate_variable(extracted, variable_config)

            # Step 6: Process raster (nodata, ROI, statistics)
            raster_result = self._processing_service.process(
                data=extracted.data,
                metadata=metadata,
                nodata_value=extracted.nodata_value,
                config=processing_config,
            )

            # Step 7: Write GeoTIFF (tmp → atomic move)
            file_path_str = self._writer.write(
                data=raster_result.data,
                metadata=raster_result.metadata,
                source=self._source_code.lower(),
                variable=variable_name,
                acquisition_datetime=extracted.acquisition_date,
                processing_version=processing_version,
                nodata_value=extracted.nodata_value,
            )

            # Step 8: Persist layer
            stats = raster_result.statistics
            layer = ProcessedLayer(
                raw_file_id=raw_file_id,
                processing_job_id=job_id,
                source_code=self._source_code,
                variable_name=variable_name,
                file_path=file_path_str,
                crs=raster_result.metadata.crs,
                bbox=list(raster_result.metadata.bounds),
                resolution_x=raster_result.metadata.resolution[0],
                resolution_y=raster_result.metadata.resolution[1],
                width=raster_result.metadata.width,
                height=raster_result.metadata.height,
                nodata_value=extracted.nodata_value,
                min_value=stats.get("min", 0.0) or 0.0,
                max_value=stats.get("max", 0.0) or 0.0,
                mean_value=stats.get("mean", 0.0) or 0.0,
                valid_pixel_count=stats.get("valid_pixel_count", 0),
                nodata_pixel_count=stats.get("nodata_pixel_count", 0),
                acquisition_date=extracted.acquisition_date,
                processing_version=processing_version,
            )
            self._layer_repo.insert(layer)

            # Step 9: Finalize job
            warnings = raster_result.warnings
            if warnings:
                self._job_repo.update_status(
                    job_id, "completed_with_warnings", warnings=warnings
                )
                return {
                    "raw_file_id": raw_file_id,
                    "job_id": job_id,
                    "status": "completed_with_warnings",
                    "output_path": file_path_str,
                    "warnings": warnings,
                }
            else:
                self._job_repo.update_status(job_id, "completed")
                return {
                    "raw_file_id": raw_file_id,
                    "job_id": job_id,
                    "status": "completed",
                    "output_path": file_path_str,
                }

        except IdempotencySkip as e:
            self._job_repo.update_status(job_id, "skipped")
            return {
                "raw_file_id": raw_file_id,
                "job_id": job_id,
                "status": "skipped",
                "message": str(e),
            }
        except (ValidationError, ReadError, WriteError) as e:
            self._job_repo.update_status(job_id, "failed", error=str(e))
            return {
                "raw_file_id": raw_file_id,
                "job_id": job_id,
                "status": "failed",
                "error": str(e),
            }
        except Exception as e:
            self._job_repo.update_status(job_id, "failed", error=str(e))
            return {
                "raw_file_id": raw_file_id,
                "job_id": job_id,
                "status": "failed",
                "error": f"Unexpected error: {e}",
            }

    def _build_processing_config(
        self,
        roi_enabled: bool,
        roi_path: str | None,
    ) -> dict[str, Any]:
        """Build processing configuration dict.

        Args:
            roi_enabled: Whether ROI clipping is enabled.
            roi_path: Path to ROI GeoJSON file.

        Returns:
            Processing config dict.
        """
        roi_config: dict[str, Any] = {"enabled": roi_enabled}
        if roi_path:
            roi_config["path"] = roi_path

        return {"roi": roi_config}
