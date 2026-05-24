# AI Core Ecosystem (Modulo 4)

A cognitive layer that consumes outputs from Modules 1-3 (geospatial pipeline) without modifying them. Implements hexagonal architecture with provider-agnostic LLM abstraction, multi-agent orchestration via LangGraph, and observability through OpenTelemetry + audit logs.

## Architecture

```
src/ai/
├── domain/                    # Business logic — models, interfaces, constants
│   ├── constants.py           # WorkflowStatus, AiActorType, ToolType enums
│   ├── errors.py              # Custom exceptions
│   ├── interfaces.py          # ABCs: LLMProvider, ContextEngine, StateManager, etc.
│   └── models.py              # Dataclasses: WorkflowState, AgentManifest, etc.
│
├── application/               # Orchestration layer
│   ├── orchestrator.py        # LangGraph workflow (context → state → agents → consolidate)
│   └── response_consolidator.py  # Multi-agent output merging with conflict detection
│
├── infrastructure/            # Concrete implementations
│   ├── llm/
│   │   └── litellm_provider.py    # LiteLLM behind LLMProvider ABC
│   ├── context/
│   │   └── context_engine.py      # Builds context from M3 tables (read-only)
│   ├── state/
│   │   └── state_manager.py       # PostgreSQL persistence (idempotent)
│   ├── runtime/
│   │   ├── plugin_system.py       # Agent discovery + JSON Schema validation
│   │   └── agent_runtime.py       # Controlled trusted import + limits enforcement
│   ├── tools/
│   │   ├── geospatial_tools.py    # Read-only wrappers over M3 repos
│   │   └── llm_tools.py           # SummarizationTool, StructuredOutputTool
│   ├── prompts/
│   │   └── prompt_manager.py      # File-based templates + variable injection
│   └── observability/
│       ├── tracing.py             # OpenTelemetry spans (non-fatal)
│       └── audit_logger.py        # AI events → audit_logs (non-fatal)
│
└── agents/                    # Agent plugins
    └── reference_agent/       # Fixture agent for runtime validation
        ├── manifest.yaml      # YAML manifest + JSON Schema
        └── agent.py           # Minimal agent implementation
```

## Data Flow

1. **Query** → LangGraph Orchestrator receives region IDs
2. **Context Engine** reads M3 tables (read-only) → structured JSON
3. **State Manager** creates workflow state in PostgreSQL
4. **Agent Runtime** loads agents from manifests, executes with limits
5. **Tool Layer** agents call tools (geospatial queries, LLM calls)
6. **Response Consolidator** merges multi-agent outputs
7. **Observability** traces + audit logs recorded (non-fatal)

## How to Add a New Agent

1. Create directory: `src/ai/agents/my-agent/`
2. Write `manifest.yaml`:
   ```yaml
   name: my-agent
   version: 1.0.0
   entry_point: agent:MyAgent
   description: My specialized agent
   type: specialized  # or "reference"
   tools:
     - geospatial_query
     - indicator_lookup
   limits:
     max_steps: 10
     max_tokens: 4096
     timeout_seconds: 30
   output_schema:
     type: object
     required: [conclusion, confidence]
     properties:
       conclusion: {type: string}
       confidence: {type: number, minimum: 0, maximum: 1}
   ```
3. Write `agent.py`:
   ```python
   class MyAgent:
       name = "my-agent"

       def execute(self, context: dict, **kwargs) -> dict:
           # Your logic here
           return {
               "conclusion": "Your analysis",
               "confidence": 0.8,
           }
   ```
4. The PluginSystem auto-discovers via glob: `src/ai/agents/*/manifest.yaml`

## Key Design Decisions

- **M4 reads M3, never writes**: All M3 access is read-only through repository interfaces
- **No FKs to M3 tables**: References are logical (application-level validation only)
- **Non-fatal observability**: Trace/audit failures are logged but never interrupt execution
- **Controlled trusted import**: Agents can only be loaded from `src/ai/agents/`
- **Idempotent state manager**: Duplicate workflow_ids return existing state; invalid transitions are rejected

## Testing

```bash
# Unit tests (no database)
pytest tests/ai/unit/

# Integration tests (requires Docker Compose PostgreSQL)
docker compose up -d
pytest tests/ai/integration/ -m integration
```

## Dependencies

- `litellm>=1.40.0` — LLM provider abstraction
- `langgraph>=0.2.0` — Workflow orchestration
- `pydantic-ai>=0.0.20` — Output validation
- `jsonschema>=4.0` — Manifest validation
- `opentelemetry-api/sdk>=1.20.0` — Distributed tracing
