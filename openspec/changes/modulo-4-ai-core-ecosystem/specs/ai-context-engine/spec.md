# ai-context-engine Specification

## Purpose

Construir contexto estructurado para agentes a partir de los outputs geoespaciales existentes (processed_layers, regions, indicators, risk_assessments). Los agentes NO consumen datos crudos — el Context Engine resume, normaliza y estructura la información.

## Requirements

### Requirement: Context Building from Geospatial Outputs (MUST)

The Context Engine MUST read from existing `processed_geospatial_layers`, `regions`, `indicators`, and `risk_assessments` to produce structured context payloads. It MUST NOT query raw_files or ingestion tables directly.

#### Scenario: Build context for a region

- GIVEN a region with existing processed_layers, indicators, and risk_assessments
- WHEN the Context Engine is invoked for that region
- THEN it MUST return a structured JSON payload containing region metadata, latest layer summary, recent indicators, and active risk assessments
- AND it MUST NOT include raw ingestion metadata

### Requirement: Context Size Control (MUST)

The Context Engine MUST enforce a configurable maximum context size (tokens or bytes) to prevent LLM context window overflow. It SHOULD summarize or truncate data when the limit is exceeded.

#### Scenario: Context exceeds token limit

- GIVEN a region with extensive historical data
- WHEN the Context Engine builds context and the raw payload exceeds the configured limit
- THEN it MUST apply summarization (aggregate stats, date-range truncation)
- AND it MUST include a `truncated: true` flag in the output

### Requirement: Source-Independent Output Format (MUST)

The Context Engine MUST produce a normalized output format independent of the underlying data source (SMAP, SAOCOM, etc.). Source-specific details MAY be preserved in a `source_metadata` field.

#### Scenario: Multiple sources produce same structure

- GIVEN processed data from SMAP and a hypothetical SAOCOM source
- WHEN the Context Engine processes both
- THEN the top-level structure MUST be identical, differing only in `source_metadata`

### Requirement: Context Freshness (SHOULD)

The Context Engine SHOULD accept an optional `max_age_hours` parameter. If the latest data exceeds this age, the engine SHOULD include a `stale_data: true` warning.

#### Scenario: Stale data warning

- GIVEN a region whose latest processed_layer is older than `max_age_hours`
- WHEN the Context Engine builds context
- THEN it MUST include `stale_data: true` in the output
- AND it MUST include the age of the most recent data point
