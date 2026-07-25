# economy-prices Specification

## Purpose

Serves daily grain price series from MAGyP Monitor de Granos for soy, corn, wheat, and sunflower. Product and port ID mappings are maintained as seed data.

## Requirements

### Requirement: Daily Price Series Retrieval
The system MUST return daily price series via `GET /api/v1/economy/prices`.

**Parameters**: `producto` (numeric ID), `puerto` (numeric ID), `desde` (YYYY-MM-DD), `hasta` (YYYY-MM-DD).
**Source**: MAGyP Monitor de Granos JSON endpoint.
**Cache**: Redis with 1h TTL on price data.

#### Scenario: Soy prices for Rosario, last 7 days
- **GIVEN** product ID mapped to soy and port ID mapped to Rosario
- **WHEN** client calls `GET /api/v1/economy/prices?producto=18&puerto=23&desde=2026-07-17&hasta=2026-07-24`
- **THEN** response is 200 with daily arrays: `minimos`, `maximos`, `promedios`, `modal` — each with `fecha` and `valor` in ARS

#### Scenario: Stale data on MAGyP failure
- **GIVEN** MAGyP endpoint is unreachable and Redis has cached data
- **WHEN** client queries prices
- **THEN** response is 200 with cached data and `X-Stale: true` header

#### Scenario: Unknown product/port
- **GIVEN** product ID not found in seed mapping
- **WHEN** client queries prices
- **THEN** response is 400 with message indicating valid product IDs

### Requirement: Product and Port ID Mapping
The system MUST load product-to-name and port-to-name ID mappings from seed data (YAML/JSON fixtures) at startup.

#### Scenario: Mapping loaded at startup
- **GIVEN** fixture files in `data/economy/`
- **WHEN** application starts
- **THEN** soy→18, corn→?, Rosario→23 mappings are available for price queries
