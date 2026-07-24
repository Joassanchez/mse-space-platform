# data-ingestion-pipeline Specification

## Purpose

Shared arq + Redis task queue for scheduled data ingestion (weather, prices, satellite catalog updates), async satellite downloads, and cache warming. Exposes job status endpoint.

## Requirements

### Requirement: Scheduled Daily Ingestion
The system MUST execute daily background pulls via arq cron for weather forecasts, price refresh, and satellite catalog updates.

#### Scenario: Daily weather forecast pull
- **GIVEN** arq worker is running with Redis connection
- **WHEN** scheduled cron job triggers the weather ingestion task
- **THEN** task fetches forecasts for configured coordinates, normalizes to metric/UTC, stores in PostgreSQL, and warms Redis cache

### Requirement: Async Satellite Download Jobs
The system MUST process satellite download requests as arq background jobs queued by the satellite-data module.

#### Scenario: Download job lifecycle
- **GIVEN** a download job is queued with scene ID
- **WHEN** arq worker picks up the job
- **THEN** status transitions: queued → downloading → processing → completed
- **AND** result stored at `data/satellite/{platform}/{scene_id}/`
- **AND** on failure, status transitions to `failed` with error message

### Requirement: Job Status Endpoint
The system MUST expose job status via `GET /api/v1/jobs/{job_id}`.

#### Scenario: Check completed download job
- **GIVEN** a download job with `job_id` has completed
- **WHEN** client calls `GET /api/v1/jobs/{job_id}`
- **THEN** response is 200 with `{"job_id": "...", "status": "completed", "result": {"file_path": "..."}}`

#### Scenario: Check unknown job
- **GIVEN** `job_id` does not exist
- **WHEN** client calls job status endpoint
- **THEN** response is 404

### Requirement: Graceful Degradation on External API Failure
The system MUST return cached data with `X-Stale: true` header when external APIs fail during ingestion.

#### Scenario: Price refresh fails, stale cache served
- **GIVEN** MAGyP endpoint is down during scheduled price refresh
- **WHEN** ingestion job runs
- **THEN** existing cached prices are preserved, `X-Stale` flag set, and failure is logged
