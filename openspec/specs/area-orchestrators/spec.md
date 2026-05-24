# Area Orchestrators Specification

## Purpose

Area orchestration layer providing domain-specific coordination on top of generic LangGraphOrchestrator. Pre-builds context, coordinates multiple agents, transforms outputs to area-specific schemas.

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| AO-001 | Pre-build context via ContextEngine before agent execution | MUST |
| AO-002 | Calculate data_completeness per agent (found_indicators / expected_indicators) | MUST |
| AO-003 | Call LangGraphOrchestrator with pre-built context + agent manifests | MUST |
| AO-004 | Transform consolidated output to area-specific schema | MUST |
| AO-005 | Persist agent_executions records with confidence and completeness | MUST |
| AO-006 | Calculate area-level confidence_score with degradation logic | MUST |
| AO-007 | Degrade gracefully when context is incomplete | MUST |

### Requirement: AO-001 — Pre-build Context

The system MUST pre-build structured context via ContextEngineImpl.build_context() before invoking LangGraphOrchestrator.

#### Scenario: Complete context available

- GIVEN valid area_id and workflow_id
- WHEN HydricEnvironmentalOrchestrator.execute() is called
- THEN ContextEngineImpl.build_context() is invoked first
- AND context contains regions, indicators, risk_assessments

#### Scenario: Context partially incomplete

- GIVEN some indicators missing in DB
- WHEN build_context() executes
- THEN context includes available indicators
- AND context includes stale_data warnings for missing data

### Requirement: AO-002 — Calculate Data Completeness

The system MUST calculate data_completeness score per agent as ratio of found_indicators to expected_indicators.

#### Scenario: All indicators present

- GIVEN agent expects 5 indicators
- AND all 5 indicators found in context
- THEN data_completeness = 1.0

#### Scenario: Partial indicators

- GIVEN agent expects 5 indicators
- AND only 3 indicators found in context
- THEN data_completeness = 0.6

### Requirement: AO-003 — Invoke LangGraphOrchestrator

The system MUST call LangGraphOrchestrator with pre-built context and agent manifests, skipping build_context node.

#### Scenario: Normal execution

- GIVEN pre-built context and 3 agent manifests
- WHEN LangGraphOrchestrator.execute() is called
- THEN _node_build_context is skipped (context already populated)
- AND execute_agents node runs all 3 agents

### Requirement: AO-004 — Transform Output

The system MUST transform generic consolidated output into area-specific HydricEnvironmentalOutput schema.

#### Scenario: Successful transformation

- GIVEN consolidated output with 3 agent results
- WHEN transformation is applied
- THEN output matches HydricEnvironmentalOutput Pydantic schema
- AND includes soil_moisture_status, weather_condition, drought_signal

### Requirement: AO-005 — Persist Executions

The system MUST persist agent_executions records for each agent run.

#### Scenario: All agents succeed

- GIVEN 3 agents executed successfully
- WHEN finalize node runs
- THEN 3 records inserted into agent_executions table
- AND each record includes structured_output, confidence_score, data_completeness

### Requirement: AO-006 — Area Confidence Calculation

The system MUST calculate area-level confidence_score using weighted combination with degradation.

#### Scenario: High confidence across agents

- GIVEN all 3 agents have confidence >= 0.8
- AND all data_completeness >= 0.8
- THEN area_confidence = weighted_average(agent_confidences)

#### Scenario: Degraded confidence

- GIVEN one agent has data_completeness < 0.5
- WHEN area_confidence is calculated
- THEN confidence is degraded by 20%
- AND degradation is logged

### Requirement: AO-007 — Graceful Degradation

The system MUST degrade gracefully when context is incomplete rather than failing.

#### Scenario: Missing soil moisture data

- GIVEN SMAP data unavailable in context
- WHEN SoilMoistureAgent executes
- THEN agent returns low confidence output
- AND orchestrator continues with weather and drought agents
- AND final output marks soil_moisture_status as UNAVAILABLE
