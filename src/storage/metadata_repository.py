"""Metadata repository using JSON files (Slice 1).

Each ingestion job gets its own metadata.json file in data/metadata/.
"""

import json
from pathlib import Path
from typing import Optional

from src.models.job_models import IngestionJob, RawFile


class MetadataRepository:
    """JSON-based metadata repository for Slice 1.

    Stores per-job metadata in data/metadata/job_{id}.json files.
    """

    def __init__(self, metadata_dir: str | Path | None = None):
        """Initialize the repository.

        Args:
            metadata_dir: Directory for metadata files.
                         Defaults to data/metadata/ relative to project root.
        """
        if metadata_dir is None:
            # Project root is 3 levels up from src/storage/metadata_repository.py
            project_root = Path(__file__).parent.parent.parent
            self.metadata_dir = project_root / "data" / "metadata"
        else:
            self.metadata_dir = Path(metadata_dir)

        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _job_file_path(self, job_id: str) -> Path:
        """Get the metadata file path for a job.

        Args:
            job_id: Unique job identifier.

        Returns:
            Path to job_{id}.json.
        """
        return self.metadata_dir / f"job_{job_id}.json"

    def save_job(self, job: IngestionJob) -> None:
        """Save or update an ingestion job's metadata.

        Args:
            job: The IngestionJob to persist.
        """
        file_path = self._job_file_path(job.job_id)
        data = job.model_dump(mode="json")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        """Read an ingestion job from its metadata file.

        Args:
            job_id: Unique job identifier.

        Returns:
            IngestionJob if found, None otherwise.
        """
        file_path = self._job_file_path(job_id)
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return IngestionJob(**data)

    def save_file(self, raw_file: RawFile, job_id: str) -> None:
        """Save a single raw file record to a job's metadata.

        Reads the existing job, appends the file, and re-saves.

        Args:
            raw_file: The RawFile to add.
            job_id: Parent job identifier.
        """
        job = self.get_job(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found in metadata repository")

        job.files.append(raw_file)
        self.save_job(job)

    def check_file_registered(
        self,
        file_name: str,
        size_bytes: int,
        job_id: str,
    ) -> Optional[RawFile]:
        """Check if a file is already registered in any job's metadata.

        Uses composite key: file_name + size_bytes.

        Args:
            file_name: The file name to check.
            size_bytes: Expected file size.
            job_id: Current job ID (to also check within this job).

        Returns:
            RawFile if found and checksum matches, None otherwise.
        """
        # Check current job first
        job = self.get_job(job_id)
        if job:
            for f in job.files:
                if f.file_name == file_name and f.size_bytes == size_bytes:
                    return f

        # Check all other job metadata files
        for meta_file in self.metadata_dir.glob("job_*.json"):
            if meta_file.name == f"job_{job_id}.json":
                continue  # Already checked

            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for file_entry in data.get("files", []):
                    if (
                        file_entry.get("file_name") == file_name
                        and file_entry.get("size_bytes") == size_bytes
                    ):
                        return RawFile(**file_entry)
            except (json.JSONDecodeError, KeyError):
                continue

        return None

    def list_all_jobs(self) -> list[IngestionJob]:
        """List all jobs in the metadata repository.

        Returns:
            List of IngestionJob objects.
        """
        jobs = []
        for meta_file in self.metadata_dir.glob("job_*.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                jobs.append(IngestionJob(**data))
            except (json.JSONDecodeError, KeyError):
                continue
        return jobs
