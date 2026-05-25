# Jobs API — Specification

## Purpose

Expose job status for scheduled and on-demand analysis jobs. Allow triggering on-demand analysis from the dashboard. Provide real-time updates via WebSocket.

## Requirements

### Requirement: List jobs

The system MUST expose GET /api/v1/jobs/ returning a list of jobs with status, filterable by status, region_id, date_from, and date_to.

#### Scenario: Returns filtered job list

- GIVEN jobs exist for cordoba_pilot with various statuses
- WHEN GET /api/v1/jobs/?region_id=cordoba_pilot&status=completed
- THEN the system MUST return only completed jobs for cordoba_pilot

### Requirement: Single job detail

The system MUST expose GET /api/v1/jobs/{job_id} returning job detail and progress.

#### Scenario: Returns job detail

- GIVEN job "job-123" exists
- WHEN GET /api/v1/jobs/job-123
- THEN the system MUST return job_id, status, region_id, areas, progress_pct, created_at, and finished_at

### Requirement: Trigger on-demand analysis

The system MUST expose POST /api/v1/jobs/trigger/ accepting { region_id, areas[], date_from, date_to } and returning a new job with ws_channel for WebSocket connection.

#### Scenario: Creates on-demand job

- GIVEN valid region_id "cordoba_pilot" and areas ["hydric_environmental"]
- WHEN POST /api/v1/jobs/trigger/ with body { "region_id": "cordoba_pilot", "areas": ["hydric_environmental"], "date_from": "2024-01-01", "date_to": "2024-01-15" }
- THEN the system MUST return 201 with job_id, status: "pending", and ws_channel
- AND the system MUST create a job record in the database

### Requirement: Job execution logs

The system MUST expose GET /api/v1/jobs/{job_id}/logs/ returning execution logs for debugging.

#### Scenario: Returns job logs

- GIVEN job "job-123" has execution logs
- WHEN GET /api/v1/jobs/job-123/logs/
- THEN the system MUST return a list of log entries with timestamp, level, and message

### Requirement: WebSocket channel per job

The system MUST expose WS /ws/jobs/{job_id} for real-time job progress. The server MUST emit job.started, job.progress, job.completed, and job.failed events.

#### Scenario: WebSocket emits job lifecycle events

- GIVEN a client connects to ws/jobs/job-123
- WHEN the AI Core starts processing job-123
- THEN the server MUST emit { event: "job.started", job_id, started_at }
- WHEN an area completes
- THEN the server MUST emit { event: "job.progress", area, pct_complete }
- WHEN all areas complete
- THEN the server MUST emit { event: "job.completed", job_id, finished_at, result_url }

#### Scenario: WebSocket handles job failure

- GIVEN a client is connected to ws/jobs/job-123
- WHEN job-123 fails during execution
- THEN the server MUST emit { event: "job.failed", job_id, error_message, failed_at }
