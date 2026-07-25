# satellite-data Specification

## Purpose

Provides SMAP soil moisture metadata search, Sentinel-1/2 catalog search, and async download of Sentinel products. Downloads run as arq background jobs. Raw files stored locally behind a storage interface.

## Requirements

### Requirement: SMAP Soil Moisture Metadata Search
The system MUST return SMAP soil moisture scene metadata via `GET /api/v1/satellite/smap`.

**Parameters**: `bbox` (min_lon,min_lat,max_lon,max_lat), `start_date`, `end_date`.
**Auth**: Earthdata credentials from Pydantic-Settings config.

#### Scenario: Search SMAP for Pergamino bounding box
- **GIVEN** valid Earthdata credentials configured
- **WHEN** client queries `GET /api/v1/satellite/smap?bbox=-61,-34,-60,-33&start_date=2026-01-01&end_date=2026-01-31`
- **THEN** response is 200 with array of scene metadata (scene_id, acquisition_date, granule_ur)
- **AND** Earthdata auth token handled transparently

### Requirement: Sentinel Catalog Search
The system MUST search Sentinel-1/2 catalogs via CDSE STAC API at `GET /api/v1/satellite/sentinel/search`.

**Parameters**: `bbox`, `start_date`, `end_date`, `platform` (sentinel-1|sentinel-2), `max_cloud_cover` (optional).

#### Scenario: Search Sentinel-2 scenes with cloud filter
- **GIVEN** CDSE credentials configured
- **WHEN** client queries sentinel search with `platform=sentinel-2&max_cloud_cover=10`
- **THEN** response is 200 with filtered scene list (id, acquisition, cloud_cover, thumbnail_url)

### Requirement: Async Sentinel Download
The system MUST accept download requests via `POST /api/v1/satellite/sentinel/{id}/download` and return a `job_id` for async processing via arq.

#### Scenario: Queue a Sentinel download
- **GIVEN** a valid Sentinel scene `id`
- **WHEN** client POSTs to the download endpoint
- **THEN** response is 202 with `{"job_id": "uuid", "status": "queued"}`
- **AND** raw file saved to `data/satellite/{platform}/{id}/` behind storage interface

#### Scenario: Download for unknown scene
- **GIVEN** an invalid or non-existent scene `id`
- **WHEN** client POSTs to download endpoint
- **THEN** response is 404
