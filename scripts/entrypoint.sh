#!/bin/bash
# MSE Space Platform — Docker entrypoint
#
# Usage:
#   docker run <image>                          # Default: Módulo 1 (ingesta SMAP)
#   docker run <image> --help
#   docker run <image> ingest --bbox ...        # Módulo 1
#   docker run <image> geospatial --limit 5     # Módulo 2
#
# If no arguments or first arg starts with '-', run Módulo 1 (backward compat).
# If first arg is "ingest", run Módulo 1 CLI.
# If first arg is "geospatial", run Módulo 2 CLI.

set -e

MODE="${1:-}"

case "$MODE" in
    ingest)
        shift
        exec python -m src.jobs.run_smap_ingestion "$@"
        ;;
    geospatial)
        shift
        exec python -m src.geospatial.cli.process_smap "$@"
        ;;
    -*|"")
        # Default / backward compat: Módulo 1
        exec python -m src.jobs.run_smap_ingestion "$@"
        ;;
    *)
        # Unknown command, pass to Módulo 1 as-is (backward compat)
        exec python -m src.jobs.run_smap_ingestion "$@"
        ;;
esac
