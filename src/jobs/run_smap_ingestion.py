"""CLI entry point for SMAP ingestion jobs.

Usage:
    python -m src.jobs.run_smap_ingestion --bbox -58.5,-35.0,-58.0,-34.5 \
        --start-date 2024-01-01 --end-date 2024-01-07

    python -m src.jobs.run_smap_ingestion --bbox -58.5,-35.0,-58.0,-34.5 \
        --start-date 2024-01-01 --end-date 2024-01-07 --search-only

    python -m src.jobs.run_smap_ingestion --config path/to/sources.yaml \
        --bbox -58.5,-35.0,-58.0,-34.5 --start-date 2024-01-01 --end-date 2024-01-07
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config.config_loader import load_sources_config
from src.ingestion.smap.smap_connector import (
    AuthenticationError,
    BboxError,
    DateRangeError,
    SmapConnector,
)
from src.jobs.job_manager import JobManager
from src.models.job_models import IngestionJob, JobState, RawFileStatus
from src.storage.metadata_repository import MetadataRepository

console = Console()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="SMAP Data Ingestion — Download SPL4SMGP.008 products from NASA Earthdata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search and download for a 7-day range
  python -m src.jobs.run_smap_ingestion \\
      --bbox -58.5,-35.0,-58.0,-34.5 \\
      --start-date 2024-01-01 --end-date 2024-01-07

  # Search only (no download)
  python -m src.jobs.run_smap_ingestion \\
      --bbox -58.5,-35.0,-58.0,-34.5 \\
      --start-date 2024-01-01 --end-date 2024-01-07 \\
      --search-only

  # Use custom config file
  python -m src.jobs.run_smap_ingestion \\
      --config /path/to/sources.yaml \\
      --bbox -58.5,-35.0,-58.0,-34.5 \\
      --start-date 2024-01-01 --end-date 2024-01-07
        """,
    )

    parser.add_argument(
        "--bbox",
        type=str,
        required=True,
        help="Bounding box as comma-separated values: min_lon,min_lat,max_lon,max_lat",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date in ISO format (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date in ISO format (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--search-only",
        action="store_true",
        default=False,
        help="List search results without downloading files",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to sources.yaml configuration file",
    )
    parser.add_argument(
        "--metadata-backend",
        type=str,
        default="json",
        choices=["json", "postgresql"],
        help="Metadata storage backend: json (default, local file) or postgresql (production, requires PostgreSQL)",
    )

    return parser.parse_args(argv)


def parse_bbox(bbox_str: str) -> list[float]:
    """Parse bbox string into list of floats.

    Args:
        bbox_str: Comma-separated bbox string.

    Returns:
        [min_lon, min_lat, max_lon, max_lat]

    Raises:
        ValueError: If bbox format is invalid.
    """
    parts = bbox_str.split(",")
    if len(parts) != 4:
        raise ValueError(
            f"bbox must have 4 comma-separated values, got {len(parts)}: {bbox_str}"
        )
    return [float(p.strip()) for p in parts]


def display_search_results(results: list) -> None:
    """Display search results in a Rich table.

    Args:
        results: List of RawFile objects (from job.files) or DataGranule objects.
    """
    table = Table(title=f"Found {len(results)} SMAP product(s)")
    table.add_column("#", style="dim")
    table.add_column("Granule ID")
    table.add_column("Acquisition Date")
    table.add_column("File Name")
    table.add_column("Size (MB)", justify="right")

    from src.models.job_models import RawFile

    for i, item in enumerate(results, 1):
        if isinstance(item, RawFile):
            # Already extracted — use RawFile fields directly
            granule_id = item.granule_id or "N/A"
            acq_date = item.acquisition_date or "N/A"
            file_name = item.file_name or "N/A"
            size_mb = item.size_bytes / (1024 * 1024) if item.size_bytes else 0
        else:
            # Raw earthaccess DataGranule — extract from UMM dict
            if isinstance(item, dict):
                umm = item.get("umm", item)
            else:
                umm = item.get("umm", {})
            granule_id = umm.get("GranuleUR", "N/A")
            temporal = umm.get("TemporalExtent", {}).get("RangeDateTime", {})
            acq_date = temporal.get("BeginningDateTime", "N/A")[:10] if temporal.get("BeginningDateTime") else "N/A"
            urls = umm.get("RelatedUrls", [])
            file_name = "N/A"
            for u in urls:
                if u.get("Type") == "GET DATA":
                    file_name = u["URL"].split("/")[-1]
                    break
            raw_size = umm.get("DataGranule", {}).get("ArchiveAndDistributionInformation", [{}])
            size_mb = raw_size[0].get("Size", 0) / (1024 * 1024) if raw_size else 0

        table.add_row(
            str(i),
            granule_id[:40] + "..." if len(granule_id) > 40 else granule_id,
            acq_date,
            file_name[:35] + "..." if len(file_name) > 35 else file_name,
            f"{size_mb:.1f}",
        )

    console.print(table)


def display_job_result(job: IngestionJob) -> None:
    """Display final job status in a Rich panel.

    Args:
        job: The completed IngestionJob.
    """
    state_color = {
        JobState.COMPLETED: "green",
        JobState.COMPLETED_WITH_WARNINGS: "yellow",
        JobState.FAILED: "red",
        JobState.RUNNING: "blue",
        JobState.PENDING: "white",
    }

    color = state_color.get(job.state, "white")

    # Build file summary
    downloaded = sum(1 for f in job.files if f.status == RawFileStatus.DOWNLOADED)
    skipped = sum(1 for f in job.files if f.status == RawFileStatus.ALREADY_DOWNLOADED)
    errors = sum(1 for f in job.files if f.status == RawFileStatus.ERROR)

    file_summary = f"{downloaded} downloaded, {skipped} skipped, {errors} errors"

    panel_content = (
        f"[bold]Job ID:[/bold] {job.job_id}\n"
        f"[bold]Source:[/bold] {job.source}\n"
        f"[bold]State:[/bold] [{color}]{job.state.value}[/{color}]\n"
        f"[bold]Ready for ETL:[/bold] {'Yes' if job.ready_for_etl else 'No'}\n"
        f"[bold]Files:[/bold] {len(job.files)} total ({file_summary})\n"
        f"[bold]Date Range:[/bold] {job.start_date} to {job.end_date}\n"
        f"[bold]Search Only:[/bold] {'Yes' if job.search_only else 'No'}"
    )

    if job.errors:
        panel_content += "\n\n[bold red]Errors:[/bold red]\n"
        for err in job.errors:
            panel_content += f"  • {err}\n"

    console.print(Panel(panel_content, title="Ingestion Job Result", border_style=color))


def main(argv: list[str] | None = None) -> int:
    """Main entry point for SMAP ingestion CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    args = parse_args(argv)

    # Parse bbox
    try:
        bbox = parse_bbox(args.bbox)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        return 1

    # Load config (optional — provides defaults, not required for CLI args)
    config_path = args.config
    max_days_range = None

    if config_path:
        try:
            config = load_sources_config(config_path)
            smap_config = config.get_smap_config()
            max_days_range = smap_config.max_days_range
            console.print(f"[dim]Loaded config from {config_path}[/dim]")
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[yellow]Warning:[/yellow] Config load failed: {e}")
            console.print("[dim]Using defaults[/dim]")

    # Initialize components
    connector = SmapConnector(max_days_range=max_days_range)
    metadata_repo = MetadataRepository()
    job_manager = JobManager(
        connector=connector,
        metadata_repo=metadata_repo,
        metadata_backend=args.metadata_backend,
    )

    # Run ingestion
    mode = "search-only" if args.search_only else "download"
    console.print(f"\n[bold]Starting SMAP ingestion ({mode})[/bold]")
    console.print(f"  Bbox: {bbox}")
    console.print(f"  Date range: {args.start_date} to {args.end_date}")
    console.print(f"  Max days range: {connector.max_days_range}\n")

    try:
        job = job_manager.run_ingestion(
            source="smap",
            bbox=bbox,
            start_date=args.start_date,
            end_date=args.end_date,
            search_only=args.search_only,
        )

        # Display results
        if job.search_only and job.files:
            display_search_results(job.files)

        display_job_result(job)

        return 0 if job.state != JobState.FAILED else 1

    except BboxError as e:
        console.print(f"[red]Bbox validation error:[/red] {e}")
        return 1
    except DateRangeError as e:
        console.print(f"[red]Date range error:[/red] {e}")
        return 1
    except AuthenticationError as e:
        console.print(f"[red]Authentication error:[/red] {e}")
        console.print("[dim]Set EARTHDATA_USERNAME and EARTHDATA_PASSWORD environment variables[/dim]")
        return 1
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
