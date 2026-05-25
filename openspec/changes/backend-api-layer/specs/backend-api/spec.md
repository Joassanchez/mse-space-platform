# Backend API — Base Specification

## Purpose

FastAPI application base providing lifespan management, middleware, shared dependencies, health/readiness endpoints, and configuration. Every other API capability depends on this foundation.

## Requirements

### Requirement: App initialization with async lifespan

The system MUST initialize the FastAPI app with an async lifespan context manager that connects to PostgreSQL and Redis on startup and disconnects on shutdown.

#### Scenario: Startup connects to all dependencies

- GIVEN the FastAPI app starts
- WHEN the lifespan context enters
- THEN the system MUST establish an async connection pool to PostgreSQL
- AND the system MUST establish an async connection to Redis

#### Scenario: Shutdown disconnects cleanly

- GIVEN the FastAPI app is shutting down
- WHEN the lifespan context exits
- THEN the system MUST close the PostgreSQL connection pool
- AND the system MUST close the Redis connection

### Requirement: Health and readiness endpoints

The system MUST expose GET /health (liveness) and GET /ready (readiness). /ready MUST verify PostgreSQL and Redis connectivity.

#### Scenario: Health returns OK

- GIVEN the app is running
- WHEN GET /health is called
- THEN the system MUST return 200 with status "ok"

#### Scenario: Ready returns OK when dependencies are up

- GIVEN PostgreSQL and Redis are reachable
- WHEN GET /ready is called
- THEN the system MUST return 200 with status "ready"

#### Scenario: Ready returns 503 when DB is down

- GIVEN PostgreSQL is unreachable
- WHEN GET /ready is called
- THEN the system MUST return 503 with status "unavailable"

### Requirement: CORS middleware

The system MUST configure CORS to accept requests only from origins specified in ALLOWED_ORIGINS env var.

#### Scenario: Request from allowed origin succeeds

- GIVEN ALLOWED_ORIGINS includes "http://localhost:3000"
- WHEN a request with Origin: http://localhost:3000 arrives
- THEN the system MUST include CORS headers in the response

### Requirement: Structured logging

The system MUST output structured JSON logs for every request with endpoint, duration_ms, status_code, and cache_hit.

#### Scenario: Request is logged with all fields

- GIVEN a client sends a request
- WHEN the request completes
- THEN the system MUST log a JSON entry with endpoint, duration_ms, status_code, and cache_hit

### Requirement: Config via pydantic-settings

The system MUST load configuration from environment variables using pydantic-settings with typed fields.

#### Scenario: Config loads from env

- GIVEN DATABASE_URL, REDIS_URL, API_KEY, and ALLOWED_ORIGINS are set in environment
- WHEN the config module loads
- THEN all values MUST be available as typed attributes
