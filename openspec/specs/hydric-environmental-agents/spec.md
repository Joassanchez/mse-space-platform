# Hydric Environmental Agents Specification

## Purpose

Domain-specific agents for Hídrico-Ambiental area: soil moisture analysis, weather monitoring, and drought classification. Each agent is a stateless plugin producing structured + template-based natural language output.

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| HEA-001 | Each agent is a plugin with manifest.yaml + execute() method | MUST |
| HEA-002 | Each agent produces structured_output + natural_language_output | MUST |
| HEA-003 | Each agent calculates confidence_score + data_completeness | MUST |
| HEA-004 | SoilMoistureAgent analyzes SMAP surface + rootzone moisture | MUST |
| HEA-005 | WeatherAgent analyzes rainfall + anomalies | MUST |
| HEA-006 | DroughtAgent analyzes SPI indicators + soil moisture for classification | MUST |
| HEA-007 | HydricEnvironmentalOrchestrator consolidates 3 agents | MUST |
| HEA-008 | Each agent is stateless (no memory between executions) | MUST |
| HEA-009 | Each agent MUST NOT access raw data or GIS DB directly | MUST |
| HEA-010 | Each agent SHOULD degrade gracefully when indicators missing | SHOULD |
| HEA-011 | Natural language output is template-based (deterministic, no LLM) | MUST |

### Requirement: HEA-001 — Plugin Architecture

Each agent MUST be implemented as a plugin with manifest.yaml defining metadata and execute(context) method.

#### Scenario: Agent discovery

- GIVEN agent directory at src/ai/agents/{name}/
- AND manifest.yaml with required fields (code, name, version, input_schema, output_schema)
- WHEN PluginSystem scans agents directory
- THEN agent is registered and available for orchestration

### Requirement: HEA-002 — Dual Output Format

Each agent MUST produce both structured_output (JSON) and natural_language_output (string).

#### Scenario: SoilMoistureAgent output

- GIVEN valid SMAP context data
- WHEN execute() completes
- THEN structured_output includes surface_moisture, rootzone_moisture, status enum
- AND natural_language_output is human-readable summary

### Requirement: HEA-003 — Confidence and Completeness

Each agent MUST calculate confidence_score and data_completeness for its execution.

#### Scenario: Full data available

- GIVEN all expected indicators present and fresh
- WHEN confidence is calculated
- THEN confidence_score >= 0.8
- AND data_completeness = 1.0

#### Scenario: Partial data

- GIVEN 3 of 5 expected indicators present
- WHEN confidence is calculated
- THEN data_completeness = 0.6
- AND confidence_score reflects weighted combination

### Requirement: HEA-004 — Soil Moisture Analysis

SoilMoistureAgent MUST analyze SMAP surface (0-5cm) and rootzone (0-100cm) soil moisture data.

#### Scenario: Normal conditions

- GIVEN surface_moisture = 0.35, rootzone_moisture = 0.40
- WHEN status is evaluated
- THEN status = ADEQUATE
- AND output includes both depth layers

#### Scenario: Dry conditions

- GIVEN surface_moisture = 0.12, rootzone_moisture = 0.18
- WHEN status is evaluated
- THEN status = DRY
- AND natural_language_output warns about low moisture

### Requirement: HEA-005 — Weather Analysis

WeatherAgent MUST analyze climate data including rainfall totals and temperature anomalies.

#### Scenario: Rainfall deficit

- GIVEN rainfall_30d = 20mm, historical_avg = 80mm
- WHEN anomaly is calculated
- THEN rainfall_anomaly = -75%
- AND condition = BELOW_AVERAGE

### Requirement: HEA-006 — Drought Classification

DroughtAgent MUST analyze SPI (Standardized Precipitation Index) indicators combined with soil moisture for drought classification.

#### Scenario: Moderate drought

- GIVEN SPI_3mo = -1.2, soil_moisture = DRY
- WHEN drought classification is evaluated
- THEN drought_signal = MODERATE_DROUGHT
- AND confidence reflects SPI reliability

#### Scenario: No drought

- GIVEN SPI_3mo = 0.5, soil_moisture = ADEQUATE
- WHEN drought classification is evaluated
- THEN drought_signal = NO_DROUGHT

### Requirement: HEA-007 — Orchestrator Consolidation

HydricEnvironmentalOrchestrator MUST consolidate outputs from all 3 agents into unified HydricEnvironmentalOutput.

#### Scenario: All agents succeed

- GIVEN SoilMoistureAgent, WeatherAgent, DroughtAgent all return valid outputs
- WHEN consolidator merges results
- THEN HydricEnvironmentalOutput contains all 3 sub-agent outputs
- AND area_confidence is calculated

### Requirement: HEA-008 — Stateless Execution

Each agent MUST be stateless with no memory or state between executions.

#### Scenario: Multiple executions

- GIVEN agent executed at t1 with context C1
- WHEN agent executed at t2 with context C2
- THEN output depends only on C2
- AND no state from C1 influences result

### Requirement: HEA-009 — No Direct Data Access

Each agent MUST NOT access raw data tables or GIS database directly — only via pre-built context.

#### Scenario: Agent receives context

- GIVEN context built by ContextEngine
- WHEN agent executes
- THEN agent reads only from context payload
- AND agent makes no direct DB queries

### Requirement: HEA-010 — Graceful Degradation

Each agent SHOULD degrade gracefully when expected indicators are missing from context.

#### Scenario: Missing SPI data

- GIVEN DroughtAgent expects SPI_3mo, SPI_6mo but only SPI_3mo present
- WHEN agent executes
- THEN agent uses available SPI_3mo only
- AND confidence_score is reduced
- AND output indicates partial analysis

### Requirement: HEA-011 — Template-Based NL Output

Natural language output MUST be generated via deterministic templates, not LLM calls inside agents.

#### Scenario: SoilMoistureAgent template

- GIVEN surface=AVERAGE, rootzone=DRY
- WHEN template is applied
- THEN output = "Superficie: humedad promedio. Raíz: humedad baja."
- AND output is deterministic (same input → same output)
