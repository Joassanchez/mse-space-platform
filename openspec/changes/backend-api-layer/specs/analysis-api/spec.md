# Analysis API — Specification

## Purpose

Expose structured outputs and natural language summaries from agent executions. All endpoints are read-only and consume the agent_executions table via ORM views.

## Requirements

### Requirement: List agent executions with pagination

The system MUST expose GET /api/v1/analysis/ returning paginated agent executions, filterable by region_id, area, date_from, date_to, and status.

#### Scenario: Returns filtered and paginated results

- GIVEN the agent_executions table contains 50 records for cordoba_pilot
- WHEN GET /api/v1/analysis/?region_id=cordoba_pilot&limit=10&page=1
- THEN the system MUST return 10 items with total=50, page=1, limit=10

### Requirement: Single execution detail

The system MUST expose GET /api/v1/analysis/{execution_id} returning the full execution detail including structured_output and natural_language.

#### Scenario: Returns full execution detail

- GIVEN an execution with id "abc-123" exists
- WHEN GET /api/v1/analysis/abc-123
- THEN the system MUST return execution_id, structured_output, natural_language, confidence_score, and data_completeness

#### Scenario: Returns 404 for unknown execution

- GIVEN no execution with id "unknown" exists
- WHEN GET /api/v1/analysis/unknown
- THEN the system MUST return 404

### Requirement: Latest execution per region and area

The system MUST expose GET /api/v1/analysis/latest/ returning the most recent completed execution for a given region_id and optional area.

#### Scenario: Returns latest analysis for region

- GIVEN region_id=cordoba_pilot has completed executions
- WHEN GET /api/v1/analysis/latest/?region_id=cordoba_pilot
- THEN the system MUST return the single most recent execution with overall_condition, confidence_score, and natural_language_summary

### Requirement: Aggregated summary

The system MUST expose GET /api/v1/analysis/summary/ returning an aggregated view of hydric condition, risk level, and active alerts for a region and date.

#### Scenario: Returns summary for region and date

- GIVEN region_id=cordoba_pilot has data for 2024-01-15
- WHEN GET /api/v1/analysis/summary/?region_id=cordoba_pilot&date=2024-01-15
- THEN the system MUST return a summary with overall_condition, risk_level, and active_alerts_count
