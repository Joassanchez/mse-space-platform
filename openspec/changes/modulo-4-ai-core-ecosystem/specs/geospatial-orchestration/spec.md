# Delta for geospatial-orchestration

## ADDED Requirements

### Requirement: Data Consumption by External Orchestrator (MAY)

The `GeospatialOrchestrator` MAY expose a read-only query interface for the M4 Master Orchestrator to discover available processed_layers, regions, and indicators. This interface MUST NOT modify pipeline state, trigger reprocessing, or alter job status. The M4 orchestrator reads — it does not control — the ETL pipeline.

#### Scenario: M4 queries available processed layers

- GIVEN an M4 Master Orchestrator needing context for a workflow
- WHEN it queries the GeospatialOrchestrator for available data
- THEN it receives a read-only view of processed_layers, regions, and indicators
- AND no pipeline state is modified

#### Scenario: M4 cannot trigger ETL pipeline

- GIVEN an M4 Master Orchestrator attempting to modify pipeline state
- WHEN it calls a write method on the GeospatialOrchestrator
- THEN the call is rejected or has no effect on pipeline execution
- AND the ETL pipeline continues operating independently

### Requirement: Non-Interference Guarantee (SHOULD)

The M4 orchestrator SHOULD be stateless from the ETL pipeline's perspective. The M4 orchestrator MUST NOT create, modify, or delete `geospatial_processing_jobs`, `processed_geospatial_layers`, or `raw_files`.

#### Scenario: M4 consumes without side effects

- GIVEN a fully processed set of layers in the ETL pipeline
- WHEN the M4 orchestrator reads them multiple times
- THEN the ETL pipeline state is unchanged
- AND all records remain identical between reads
