# Backend Cache — Specification

## Purpose

Redis cache layer to reduce load on PostgreSQL/PostGIS for read-heavy endpoints. TTL-based with tag invalidation.

## Requirements

### Requirement: Cache GET responses with TTL

The system MUST cache responses for configured GET endpoints using Redis, with TTL values per endpoint as defined in configuration.

#### Scenario: Cached response returns within TTL

- GIVEN GET /api/v1/analysis/latest/?region_id=cordoba_pilot was called 2 minutes ago with TTL=5min
- WHEN the same request arrives again
- THEN the system MUST return the cached response
- AND the response MUST include a cache_hit: true header

#### Scenario: Expired cache returns fresh data

- GIVEN GET /api/v1/analysis/latest/?region_id=cordoba_pilot was cached 6 minutes ago with TTL=5min
- WHEN the same request arrives
- THEN the system MUST query the database and return fresh data

### Requirement: Cache key pattern

Cache keys MUST follow the pattern {endpoint}:{region_id}:{date_param} for consistent invalidation.

#### Scenario: Key includes endpoint, region, and date

- GIVEN a request to /api/v1/geo/soil-moisture/?region_id=cordoba_pilot&date=2024-01-15
- WHEN the response is cached
- THEN the cache key MUST be "geo:soil-moisture:cordoba_pilot:2024-01-15"

### Requirement: Cache TTL values

The system MUST apply the following default TTLs:
- /analysis/ endpoints: 5 min
- /geo/ endpoints: 10 min
- /alerts/active/count: 1 min
- /regions/: 60 min

#### Scenario: Applies correct TTL per endpoint

- GIVEN a request to /api/v1/regions/
- WHEN the response is cached
- THEN the TTL MUST be 3600 seconds

### Requirement: Cache invalidation

The system MUST support cache invalidation for specific patterns. Invalidation SHOULD be triggered by tag-based Redis keyspace notifications when available, or by direct invalidation call.

#### Scenario: Invalidates cache by pattern

- GIVEN the cache contains entries for geo:soil-moisture:cordoba_pilot:*
- WHEN an invalidation for pattern "geo:soil-moisture:cordoba_pilot:*" is triggered
- THEN all matching cache entries MUST be deleted
