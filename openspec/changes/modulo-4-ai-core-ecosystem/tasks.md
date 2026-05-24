# Tasks: MÃ³dulo 4 â€” AI Core Ecosystem

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 900-1100 lines |
| 400-line budget risk | Medium (budget configurado: 1200) |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Slice 1: Foundation) â†’ PR 2 (Slice 2: Orchestration) â†’ PR 3 (Slice 3: Hardening) |
| Delivery strategy | auto-forecast |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Slice 1: Preflight, domain, migration 004, LiteLLM, Context Engine, State Manager, reference agent | PR 1 | Base: main. Tests de slice corren contra M1-M3 reales + nuevos |
| 2 | Slice 2: LangGraph, Agent Runtime, Plugin System, Tools, Prompts, Response Consolidation | PR 2 | Base: main. Depende de interfaces de Slice 1 |
| 3 | Slice 3: Observability, hardening, tests exhaustivos, docs | PR 3 | Base: main. Cierre del mÃ³dulo |

## Phase 0: Preflight â€” Repo Validation

- [x] 0.1 Verificar estructura real del repo: `src/`, `migrations/`, `tests/`, `requirements.txt`, `docker-compose.yml`
- [x] 0.2 Verificar ubicación y contenido de ``requirements.txt`` — confirmar formato y secciones existentes
- [x] 0.3 Verificar estado real de M3: tablas `processed_geospatial_layers`, `regions`, `indicators`, `risk_assessments`, `audit_logs` existen
- [x] 0.4 Inspeccionar `audit_logs` real: obtener nombre exacto del CHECK constraint de `actor_type` con `psql \d+ audit_logs` o consulta `information_schema`
- [x] 0.5 Verificar patrÃ³n de migraciones existentes: formato (SQL transactional, BEGIN/COMMIT, naming `NNN_name.sql`), idempotencia (`IF NOT EXISTS`), orden de ejecuciÃ³n
- [x] 0.6 Verificar patrÃ³n de tests existentes: estructura `tests/unit/`, `tests/integration/`, conftest.py, fixtures de Docker Compose para integraciÃ³n
- [x] 0.7 Verificar cÃ³mo se ejecutan tests de integraciÃ³n actualmente (Docker Compose service vs. fixture directa)
- [x] 0.8 Confirmar que `docker-compose.yml` ya tiene servicio PostgreSQL con PostGIS (M3) â€” NO crear `docker-compose.test.yml` nuevo, reutilizar/extender el existente

## Phase 1: Domain Foundation (Slice 1)

- [x] 1.1 Create `src/ai/__init__.py`
- [x] 1.2 Create `src/ai/domain/constants.py` con enums propios de M4: `WorkflowStatus`, `AiActorType` (system, user, agent, reference_agent), `ToolType`
- [x] 1.3 Create `src/ai/domain/errors.py` con `ManifestValidationError`, `AgentExecutionError`, `ToolExecutionError`, `ContextError`
- [x] 1.4 Create `src/ai/domain/models.py` con dataclasses: `WorkflowState`, `ExecutionTrace`, `AgentManifest`, `ToolResult`, `LLMRequest`, `LLMResponse`, `ExecutionLimits`
- [x] 1.5 Create `src/ai/domain/interfaces.py` con ABCs: `LLMProvider`, `ContextEngine`, `StateManager`, `AgentRuntime`, `Tool`, `PromptTemplate`

## Phase 2: Database Migration (Slice 1)

- [x] 2.1 Create `migrations/004_ai_foundation.sql`: tablas `ai_workflow_states`, `ai_execution_traces`, `ai_prompt_metadata` con `IF NOT EXISTS`, transactional, idempotente
- [x] 2.2 Inspeccionar CHECK constraint real de `audit_logs.actor_type` (inspecciÃ³n de Phase 0). Si no incluye `'agent'`, migraciÃ³n no destructiva: `ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS ...; ALTER TABLE audit_logs ADD CONSTRAINT ... CHECK (actor_type IN ('system', 'user', 'agent'))`
- [x] 2.3 Update `requirements.txt`: agregar `litellm>=1.40.0`, `pydantic-ai>=0.0.20`, `langgraph>=0.2.0`, `pyyaml>=6.0` (YAML manifests), `jsonschema>=4.0` (manifest validation)

## Phase 3: LLM Abstraction Layer (Slice 1)

- [x] 3.1 Create `src/ai/infrastructure/llm/__init__.py`
- [x] 3.2 Create `src/ai/infrastructure/llm/litellm_provider.py` implementando `LLMProvider` ABC con `complete()` y `set_provider()`. Provider vÃ­a env vars (`LITELLM_DEFAULT_MODEL`, `LITELLM_PROVIDERS`)
- [x] 3.3 Unit tests: LiteLLM provider mockeado, switching de provider, error handling (rate limit retry, auth error no retry)

## Phase 4: Context Engine (Slice 1)

- [x] 4.1 Create `src/ai/infrastructure/context/__init__.py`
- [x] 4.2 Create `src/ai/infrastructure/context/context_engine.py` implementando `build_context()`: lee de `processed_geospatial_layers`, `regions`, `indicators`, `risk_assessments` vÃ­a repos read-only. Output: JSON estructurado con selecciÃ³n de campos relevantes por entidad
- [x] 4.3 Implementar `summarize_context()`: selecciÃ³n estructurada de campos relevantes (no solo truncaciÃ³n por tokens), lÃ­mite configurable por entidad (max_layers, max_indicators, max_risks), metadata de contexto (# entidades, rango temporal, fecha de generaciÃ³n), warnings cuando se recorta informaciÃ³n
- [x] 4.4 Implementar `stale_data` warning: si latest data supera `max_age_hours`, incluir `stale_data: true` + edad del dato mÃ¡s reciente en el output
- [x] 4.5 Unit tests: context building con datos mock, summarization con lÃ­mites, stale_data warning

## Phase 5: State Manager (Slice 1)

- [x] 5.1 Create `src/ai/infrastructure/state/__init__.py`
- [x] 5.2 Create `src/ai/infrastructure/state/state_manager.py` implementando `create_state()`, `update_state()`, `persist_trace()` contra `ai_workflow_states` y `ai_execution_traces`
- [x] 5.3 Integration tests: CRUD de workflow states + traces contra PostgreSQL real (Docker Compose existente)

## Phase 6: Reference Agent (Slice 1)

- [x] 6.1 Create `src/ai/agents/__init__.py`
- [x] 6.2 Create `src/ai/agents/reference_agent/manifest.yaml` con `type: reference`, tool allowlist, `output_schema`, `limits`. Solo para validar runtime â€” sin lÃ³gica de dominio
- [x] 6.3 Create `src/ai/agents/reference_agent/agent.py`: agente fixture mÃ­nimo que recibe contexto, ejecuta tool allowlist, produce output estructurado. Sin lÃ³gica especializada de dominio
- [x] 6.4 Unit test: manifest reference agent se valida contra JSON Schema
- [x] 6.5 Integration test: runtime carga reference agent, ejecuta con contexto mock, valida output

## Phase 7: LangGraph Orchestrator (Slice 2)

- [x] 7.1 Create `src/ai/application/__init__.py`
- [x] 7.2 Create `src/ai/application/orchestrator.py` con LangGraph: workflow definition, state machine, step orchestration. Orchestrator coordina Context Engine + State Manager + Agent Runtime
- [x] 7.3 Implement workflow state transitions: `pending → running → completed | failed`
- [x] 7.4 Create `src/ai/application/response_consolidator.py`: merge de outputs estructurados multiagente en respuesta unificada

## Phase 8: Agent Runtime & Plugin System (Slice 2)

- [x] 8.1 Create `src/ai/infrastructure/runtime/__init__.py`
- [x] 8.2 Create `src/ai/infrastructure/runtime/plugin_system.py`: manifest discovery (glob de `src/ai/agents/*/manifest.yaml`), JSON Schema validation, agent registration
- [x] 8.3 Create `src/ai/infrastructure/runtime/agent_runtime.py`: `load_agent()` con import controlado (solo `src/ai/agents/`), `execute()` con enforcement de limits, `validate_output()` con validación estructural (JSON Schema/Pydantic)
- [x] 8.4 Implement execution limits: `max_steps`, `max_tokens`, `timeout_seconds`
- [x] 8.5 Implement tool allowlist: agent solo invoca tools declaradas en su manifest

## Phase 9: Tool Layer (Slice 2)

- [x] 9.1 Create `src/ai/infrastructure/tools/__init__.py`
- [x] 9.2 Create `src/ai/infrastructure/tools/geospatial_tools.py`: wrappers **read-only** sobre repos existentes
- [x] 9.3 Create `src/ai/infrastructure/tools/llm_tools.py`: `SummarizationTool`, `StructuredOutputTool`. Wrappers sobre `LLMProvider` para uso por agentes
- [x] 9.4 Implement tool allowlist enforcement en AgentRuntime (validación contra manifest declarado)

## Phase 10: Prompt Management (Slice 2)

- [x] 10.1 Create `data/prompts/` con `.gitkeep`
- [x] 10.2 Create `src/ai/infrastructure/prompts/__init__.py`
- [x] 10.3 Create `src/ai/infrastructure/prompts/prompt_manager.py`: carga templates desde archivos versionados en `data/prompts/`, metadata desde `ai_prompt_metadata` (overrides de producciÃ³n)
- [x] 10.4 Create system prompt maestro en `data/prompts/maestro.md`: identidad global, reglas de output, constraints
- [x] 10.5 Implement variable injection con `MissingVariableWarning` si hay variables no definidas

## Phase 11: Observability & Hardening (Slice 3)

- [x] 11.1 Create `src/ai/infrastructure/observability/__init__.py`
- [x] 11.2 Create `src/ai/infrastructure/observability/tracing.py`: OpenTelemetry spans para workflow steps, tool calls, LLM invocations
- [x] 11.3 Create `src/ai/infrastructure/observability/audit_logger.py`: escribe eventos AI en `audit_logs` con `entity_type` (ai_workflow, ai_agent, ai_tool_call) y metadata JSONB (workflow_id, agent_id, model, token_usage, duration_ms)
- [x] 11.4 Implement non-fatal audit: fallo de trace/audit se loggea pero NO interrumpe ejecuciÃ³n
- [x] 11.5 Add idempotency checks en transiciones de workflow state
- [x] 11.6 Update `requirements.txt`: agregar `opentelemetry-api`, `opentelemetry-sdk`

## Phase 12: Tests por Slice (Regression Gate)

Cada slice/PR debe pasar su propia puerta de regresiÃ³n antes de mergear:

- [x] 12.1 **Slice 1 tests**: unit tests nuevos (domain, LLMProvider, ContextEngine, StateManager, manifest validation) + integration tests con Docker Compose existente (state CRUD, context building contra M3 real) + tests M1-M3 existentes que correspondan
- [x] 12.2 **Slice 2 tests**: unit tests nuevos (orchestrator, runtime, plugin system, tools, prompts, response consolidation) + integration tests (workflow execution, tool layer contra M3 seedeado) + regression M1-M3
- [x] 12.3 **Slice 3 tests**: observability tests, execution limits tests, E2E full workflow + regression completa M1-M3 + typecheck/lint si existen en el proyecto
- [x] 12.4 Verificar que el patrÃ³n de Docker Compose para tests de integraciÃ³n reutiliza el existente (no crear `docker-compose.test.yml` nuevo)

## Phase 13: Documentation & Cleanup

- [x] 13.1 Create `src/ai/README.md` con architecture overview, directory structure, cÃ³mo agregar un nuevo agente
- [x] 13.2 Agregar docstrings a todos los mÃ©todos pÃºblicos en interfaces e implementaciones
- [x] 13.3 Remove temporary debug code, add type hints where missing
- [x] 13.4 VerificaciÃ³n final: M1-M3 tests siguen pasando â€” zero regressions



