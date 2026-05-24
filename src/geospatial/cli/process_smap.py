"""CLI entry point for SMAP geospatial processing.

Usage:
    python -m src.geospatial.cli.process_smap --limit 1
    python -m src.geospatial.cli.process_smap --raw-file-id 42
    python -m src.geospatial.cli.process_smap --processing-version v2 --roi-enabled

Exit codes:
    0  All jobs completed without errors
    1  One or more jobs failed
    2  Invalid arguments or configuration error
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config.config_loader import load_geospatial_config, load_sources_config
from src.geospatial.application.orchestrator import GeospatialOrchestrator
from src.geospatial.application.raster_processing_service import RasterProcessingService
from src.geospatial.infrastructure.hdf5.smap_reader import SMAPHDF5Reader
from src.geospatial.infrastructure.persistence.postgres_repositories import (
    GeospatialProcessingJobRepositoryImpl,
    ProcessedLayerRepositoryImpl,
    RawFileDiscoveryRepositoryImpl,
)
from src.geospatial.infrastructure.raster.geotiff_writer import GeoTIFFWriter

console = Console()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="SMAP Geospatial ETL — Convert raw HDF5 to GeoTIFF layers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all pending files
  python -m src.geospatial.cli.process_smap

  # Process only 1 file
  python -m src.geospatial.cli.process_smap --limit 1

  # Process a specific raw file
  python -m src.geospatial.cli.process_smap --raw-file-id 42

  # Reprocess with a new version
  python -m src.geospatial.cli.process_smap --processing-version v2

  # Disable ROI clipping
  python -m src.geospatial.cli.process_smap --no-roi

  # Use custom ROI path
  python -m src.geospatial.cli.process_smap --roi-path /path/to/roi.geojson
        """,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process up to N files (default: all)",
    )
    parser.add_argument(
        "--raw-file-id",
        type=int,
        default=None,
        help="Process a specific raw_file_id",
    )
    parser.add_argument(
        "--processing-version",
        type=str,
        default="v1",
        help="Processing version string (default: v1)",
    )
    parser.add_argument(
        "--roi-enabled",
        action="store_true",
        default=True,
        help="Enable ROI clipping (default: enabled)",
    )
    parser.add_argument(
        "--no-roi",
        action="store_true",
        default=False,
        help="Disable ROI clipping",
    )
    parser.add_argument(
        "--roi-path",
        type=str,
        default=None,
        help="Path to ROI GeoJSON file (default: from config)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to sources.yaml configuration file",
    )

    return parser.parse_args(argv)


def display_results(results: dict) -> None:
    """Display processing results in a Rich table and summary panel.

    Args:
        results: Orchestrator results dict.
    """
    total = results.get("total", 0)
    if total == 0:
        console.print(Panel(results.get("message", "No files to process"), title="SMAP Geospatial ETL"))
        return

    # Details table
    table = Table(title=f"Processed {total} file(s)")
    table.add_column("Raw File ID", style="dim")
    table.add_column("Job ID", style="dim")
    table.add_column("Status")
    table.add_column("Output Path")
    table.add_column("Message")

    status_colors = {
        "completed": "green",
        "completed_with_warnings": "yellow",
        "skipped": "blue",
        "failed": "red",
    }

    for detail in results.get("details", []):
        status = detail.get("status", "unknown")
        color = status_colors.get(status, "white")

        table.add_row(
            str(detail.get("raw_file_id", "N/A")),
            str(detail.get("job_id", ""))[:8] + "..." if detail.get("job_id") else "",
            f"[{color}]{status}[/{color}]",
            detail.get("output_path", "")[:50] or "",
            detail.get("message", detail.get("error", ""))[:60],
        )

    console.print(table)

    # Summary panel
    completed = results.get("completed", 0)
    completed_warn = results.get("completed_with_warnings", 0)
    skipped = results.get("skipped", 0)
    failed = results.get("failed", 0)

    summary = (
        f"[bold]Total:[/bold] {total}\n"
        f"[green]Completed:[/green] {completed}\n"
        f"[yellow]With Warnings:[/yellow] {completed_warn}\n"
        f"[blue]Skipped:[/blue] {skipped}\n"
        f"[red]Failed:[/red] {failed}"
    )

    border_style = "red" if failed > 0 else "green"
    console.print(Panel(summary, title="Summary", border_style=border_style))


def main(argv: list[str] | None = None) -> int:
    """Main entry point for SMAP geospatial CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 = OK, 1 = failures, 2 = invalid args).
    """
    args = parse_args(argv)

    # Validate mutually exclusive ROI flags
    if args.no_roi:
        roi_enabled = False
    else:
        roi_enabled = args.roi_enabled

    # Load configs
    config_path = args.config
    try:
        config = load_sources_config(config_path)
        sources_config = config.sources
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        return 2

    # Extract geospatial config (from geospatial-sources.yaml)
    try:
        geospatial_config = load_geospatial_config()
    except FileNotFoundError:
        geospatial_config = {}
    variable_configs = geospatial_config.get("variables", [])
    nodata_value = geospatial_config.get("nodata_value", -9999.0)

    # Resolve ROI path
    roi_path = args.roi_path
    if roi_path is None:
        roi_config = geospatial_config.get("roi", {})
        roi_path = roi_config.get("path")

    # Initialize components (dependency injection)
    reader = SMAPHDF5Reader()
    validator = None  # Will be set below
    processing_service = RasterProcessingService()
    writer = GeoTIFFWriter()
    discovery_repo = RawFileDiscoveryRepositoryImpl()
    job_repo = GeospatialProcessingJobRepositoryImpl()
    layer_repo = ProcessedLayerRepositoryImpl()

    # Import validator here to avoid circular imports
    from src.geospatial.application.smap_validation_service import SMAPValidationService

    validator = SMAPValidationService()

    # Build orchestrator
    orchestrator = GeospatialOrchestrator(
        reader=reader,
        validator=validator,
        processing_service=processing_service,
        writer=writer,
        discovery_repo=discovery_repo,
        job_repo=job_repo,
        layer_repo=layer_repo,
        source_code="SMAP",
        variable_configs=variable_configs,
    )

    # Run pipeline
    console.print(f"\n[bold]Starting SMAP Geospatial ETL[/bold]")
    console.print(f"  Processing version: {args.processing_version}")
    console.print(f"  ROI enabled: {roi_enabled}")
    if roi_path:
        console.print(f"  ROI path: {roi_path}")
    if args.limit:
        console.print(f"  Limit: {args.limit} file(s)")
    if args.raw_file_id:
        console.print(f"  Raw file ID: {args.raw_file_id}")
    console.print()

    try:
        results = orchestrator.run_batch(
            limit=args.limit,
            raw_file_id=args.raw_file_id,
            processing_version=args.processing_version,
            roi_enabled=roi_enabled,
            roi_path=roi_path,
        )

        display_results(results)

        # Exit code: 1 if any failures
        if results.get("failed", 0) > 0:
            return 1
        return 0

    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
