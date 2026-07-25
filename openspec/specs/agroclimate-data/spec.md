# agroclimate-data Specification

## Purpose

Serves weather forecasts (OpenWeather) and agroclimatic parameters (NASA POWER) for the INTA Pergamino case study area. Cached in Redis with TTL; rate-limited by IP; degrades gracefully to stale data on external API failure.

## Requirements

### Requirement: Weather Forecast Retrieval
The system MUST return current conditions and short-term forecasts for given coordinates via `GET /api/v1/agroclimate/weather`.

**Parameters**: `lat` (float), `lon` (float) — both required.
**Cache**: Redis with 1h TTL.
**Degradation**: On cache miss + API failure, return 503 with error detail.

#### Scenario: Fresh forecast hit
- **GIVEN** valid coordinates for Pergamino (-33.89, -60.57) and Redis cache is warm
- **WHEN** client calls `GET /api/v1/agroclimate/weather?lat=-33.89&lon=-60.57`
- **THEN** response is 200 with JSON containing temperature, humidity, wind, conditions
- **AND** `X-Cache: HIT` header present

#### Scenario: Cache miss triggers API call
- **GIVEN** cold cache for given coordinates
- **WHEN** client calls weather endpoint
- **THEN** system fetches from OpenWeather, caches result, returns 200
- **AND** `X-Cache: MISS` header present

#### Scenario: API failure with stale cache
- **GIVEN** Redis has cached data within 24h for the coordinates but OpenWeather API is unreachable
- **WHEN** client calls weather endpoint
- **THEN** response is 200 with cached data and `X-Stale: true` header

### Requirement: Agroclimatic Parameters Retrieval
The system MUST return NASA POWER agroclimatic parameters via `GET /api/v1/agroclimate/power`.

**Parameters**: `lat`, `lon`, `start_date`, `end_date` (YYYY-MM-DD), `parameters` (comma-separated: solar, temp, humidity, precip, wind).
**Cache**: 24h TTL.

#### Scenario: Daily parameters for a date range
- **GIVEN** coordinates for INTA Pergamino and a 30-day date range
- **WHEN** client requests `GET /api/v1/agroclimate/power?lat=-33.89&lon=-60.57&start_date=2026-01-01&end_date=2026-01-30&parameters=solar,temp,precip`
- **THEN** response is 200 with daily arrays for each requested parameter
- **AND** values in metric units (°C, MJ/m²/day, mm)

### Requirement: IP-Based Rate Limiting
The system MUST limit requests per IP across all agroclimate endpoints.

#### Scenario: Rate limit exceeded
- **GIVEN** client IP has exceeded 60 requests/minute
- **WHEN** client calls any agroclimate endpoint
- **THEN** response is 429 with `Retry-After` header
