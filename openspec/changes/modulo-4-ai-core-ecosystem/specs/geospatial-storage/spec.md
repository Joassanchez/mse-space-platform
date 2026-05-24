# Delta for geospatial-storage

## ADDED Requirements

### Requirement: Workflow State Tables (MUST)

The system MUST provide database tables for persisting multi-agent workflow execution state. These tables MUST be separate from the existing `regions`, `indicators`, `risk_assessments`, and `economic_impacts` tables. The schema MUST include: `workflow_id`, `status`, `agent_id`, `input_summary`, `output_summary`, `started_at`, `finished_at`, `duration_ms`, `token_usage`, and `parent_workflow_id` for nested workflows.

#### Scenario: Record workflow step execution

- GIVEN a multi-step workflow executing an agent
- WHEN the agent completes a step
- THEN a record is created in the workflow state table with status, duration, and token_usage
- AND the record is linked to the parent workflow

#### Scenario: Query workflow lineage

- GIVEN a workflow with nested sub-workflows
- WHEN the State Manager is queried by root workflow_id
- THEN it returns all step records ordered by execution time
- AND the parent-child relationships are resolvable

### Requirement: Non-Interference with Geospatial Storage (MUST)

Workflow state tables MUST NOT have foreign key dependencies on `processed_geospatial_layers`, `raw_files`, or `geospatial_processing_jobs`. Workflow state references geospatial data by value (layer_id, region_id) not by database FK constraint.

#### Scenario: Workflow references existing region

- GIVEN a workflow that analyzes a specific region
- WHEN the workflow state is persisted
- THEN the region_id MAY be stored as a plain integer reference
- AND there is NO database FK constraint on `regions.id`

### Requirement: State Retention Policy (SHOULD)

The system SHOULD support a configurable retention policy for workflow state records. Records older than the retention window MAY be archived or deleted.

#### Scenario: Automatic state cleanup

- GIVEN a retention policy of 90 days
- WHEN a workflow record is older than 90 days
- THEN the State Manager MAY archive or delete it
- AND active workflows are not affected
