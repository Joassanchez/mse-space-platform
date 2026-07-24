# agronomy-catalog Specification

## Purpose

Serves static reference data — BBCH phenological stages, Kc coefficients, and temperature thresholds for soy and corn — loaded from YAML/JSON fixtures at startup.

## Requirements

### Requirement: Crop Listing
The system MUST return supported crops via `GET /api/v1/agronomy/crops`.

#### Scenario: List all supported crops
- **GIVEN** seed data loaded at startup from fixtures
- **WHEN** client calls `GET /api/v1/agronomy/crops`
- **THEN** response is 200 with array of `{id, name, scientific_name}` for soy and corn

### Requirement: Crop Stage Detail
The system MUST return phenological stages, Kc coefficients, and temperature thresholds for a given crop via `GET /api/v1/agronomy/crops/{id}/stages`.

#### Scenario: Soy growth stages
- **GIVEN** crop `id` for soy exists
- **WHEN** client calls `GET /api/v1/agronomy/crops/soy/stages`
- **THEN** response is 200 with array of stages, each containing `{bbch_code, name, kc, temp_min, temp_max, temp_opt}`
- **AND** BBCH 60 = flowering, BBCH 79 = end of pod formation

#### Scenario: Unknown crop
- **GIVEN** crop `id` does not exist
- **WHEN** client calls stages endpoint
- **THEN** response is 404

### Requirement: Seed Data at Startup
The system MUST load agronomic reference data from version-controlled YAML/JSON fixtures on application startup.

#### Scenario: Startup with valid fixtures
- **GIVEN** fixture files present in `data/agronomy/`
- **WHEN** application starts
- **THEN** crop and stage data is loaded into memory and available immediately
- **AND** missing or malformed fixtures cause startup failure with clear error
