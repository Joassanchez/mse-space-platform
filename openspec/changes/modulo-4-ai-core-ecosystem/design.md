# Design: Módulo 4 — AI Core Ecosystem

## Technical Approach

M4 es una **capa cognitiva separada** que consume outputs de M1-M3 sin modificarlos. Arquitectura hexagonal: modelos e interfaces en `src/ai/domain/`, implementaciones concretas (LangGraph, LiteLLM, PostgreSQL) en `src/ai/infrastructure/`, orquestación en `src/ai/application/`.

Context Engine lee `processed_geospatial_layers`, `regions`, `indicators`, `risk_assessments` vía repositorios read-only. State Manager persiste trazas de ejecución en tablas `ai_workflow_states` y `ai_execution_traces` (separadas de M3). Master Orchestrator (LangGraph) coordina agentes con transiciones de estado explícitas.

Tres slices: Foundation (LiteLLM + Context + State), Orchestration (LangGraph + Runtime + Tools), Hardening (Observability + limits).

## Architecture Decisions

### Decision: Code Placement — Directorio `src/ai/` Separado

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| `src/ai/` (nuevo top-level) | Separación limpia, boundary explícito, no se confunde con pipeline geoespacial | ✅ ELEGIDO |
| `src/geospatial/ai/` | Cercanía pero difumina límite M3/M4, sugiere que M4 es parte del módulo geoespacial | Rechazado |

**Rationale**: M4 es **consumidor** de outputs de M3, no modificador. Directorio separado enforced el boundary arquitectónico y previene acoplamiento accidental.

### Decision: Tablas de Estado Separadas de M3

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| Nuevas `ai_workflow_states`, `ai_execution_traces` | Separación clara, ciclo de vida independiente, rollback más fácil | ✅ ELEGIDO |
| Extender `audit_logs` con metadata de IA | Schema más simple pero acopla estado de M4 a auditoría de M3, difícil consultar estado de workflow | Rechazado |
| JSONB en tablas existentes | Flexible pero pierde queryability, indexing y constraints | Rechazado |

**Rationale**: El estado de workflow es **metadata transitoria de ejecución**, no datos analíticos. Tablas separadas permiten migraciones, estrategias de indexing y políticas de retención independientes. Referencias a entidades M3 (region_id, indicator_id) son **lógicas** (sin FKs de BD) para evitar acoplamiento cruzado. `audit_logs` se reutiliza SOLO para auditoría de eventos AI (start, complete, fail), NO como almacenamiento de estado.

### Decision: Agent Manifest — YAML con Validación JSON Schema

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| YAML manifest + JSON Schema | Legible, versionable, valida estructura antes de cargar | ✅ ELEGIDO |
| Import dinámico Python no validado | Flexible pero riesgo de seguridad, difícil de auditar, sin validación estática | Rechazado |
| Import controlado de plugins locales trusted, validado por manifest + JSON Schema | Permite `entry_point` con seguridad: solo carga clases desde módulos conocidos, validación previa | ✅ Usado para `entry_point` |

**Rationale**: El `entry_point` del manifest (`agent:ReferenceAgent`) se resuelve mediante import controlado: solo módulos dentro de `src/ai/agents/` y validados por JSON Schema. No se permite import arbitrario desde fuera del árbol de agentes.

**Estructura del manifest**:
```yaml
name: reference-agent
version: 1.0.0
entry_point: agent:ReferenceAgent
description: Reference agent for testing runtime
tools:
  - geospatial_query
  - indicator_lookup
limits:
  max_steps: 10
  max_tokens: 4096
  timeout_seconds: 30
output_schema:
  type: object
  properties:
    conclusion: {type: string}
    confidence: {type: number, minimum: 0, maximum: 1}
```

### Decision: Tool Layer — Patrón Wrapper

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| Wrappers sobre servicios M2/M3 existentes | Reusa lógica existente, cero duplicación, dirección de dependencia clara | ✅ ELEGIDO |
| Implementación directa en M4 | Más control pero duplica lógica de M2/M3, riesgo de divergencia | Rechazado |

**Rationale**: Tools son **adapters** que exponen servicios M2/M3 a los agentes. Ejemplo: `GeospatialQueryTool` wrappea `RegionRepository` e `IndicatorRepository`. Agregan formato específico para LLM (prompts estructurados, parsing de output) pero delegan la lógica core a servicios existentes.

### Decision: Consumo de M3 — Referencias Lógicas, Sin FKs

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| Referencias lógicas (IDs, sin FKs) | M4 deployable/rollbackeable independientemente, sin FKs cross-schema | ✅ ELEGIDO |
| FKs a tablas M3 | Enforces integridad referencial pero acopla M4 a schema M3, bloquea migraciones independientes | Rechazado |

**Rationale**: Context Engine lee datos M3 y produce JSON estructurado. Los agentes referencian entidades por ID (region_id: 42) pero las tablas de M4 NO declaran FKs a tablas M3. La validación es a nivel de aplicación (Context Engine verifica existencia antes de retornar contexto).

### Decision: Estrategia de Observabilidad — Audit Extendido + Trazas

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| Extender `audit_logs` con `actor_type='agent'` + OpenTelemetry | Reusa infraestructura existente de auditoría, agrega tracing distribuido | ✅ ELEGIDO |
| Nueva tabla `ai_audit_logs` | Separación clara pero duplica infraestructura de auditoría, dificulta correlación M3/M4 | Rechazado |

**Rationale**: `audit_logs` se reutiliza para eventos de **auditoría** (workflow_start, agent_complete, workflow_failed). El estado transitorio de ejecución va en `ai_workflow_states`/`ai_execution_traces`. OpenTelemetry captura trazas de ejecución (pasos de LangGraph, tool calls, invocaciones LLM). Non-fatal: fallos de trace/audit se loggean pero no interrumpen la ejecución.

### Decision: Estrategia de Prompt Management

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| **Archivos versionados como fuente principal**, tabla solo para metadata/overrides | Control de versiones nativo (git), sin dependencia de BD para desarrollo local, tabla opcional para overrides en producción | ✅ ELEGIDO |
| Tabla como fuente principal, archivos como seed inicial | Requiere BD para desarrollo local, más fricción en el ciclo de edición | Rechazado |

**Rationale**: Los prompts viven como archivos YAML/MD versionados en `data/prompts/`. La tabla `ai_prompt_templates` almacena solo metadata (versión activa, override de producción, auditoría de cambios). En desarrollo, el Prompt Manager lee de archivos directamente. En producción, puede consultar la tabla para verificar si hay overrides configurados.

### Decision: Rol de PydanticAI

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| **PydanticAI para validación de outputs estructurados** | Validación de schemas, type coercion, errores descriptivos. Se integra con el AgentRuntime para validar output_schema del manifest | ✅ ELEGIDO (Slice 1) |
| PydanticAI como encapsulador de Agent Runtime | Mayor abstracción pero introduce dependencia más pesada y opaca. Postergado | Postergado a Slice 2/3 |
| No usar PydanticAI | Menos dependencias pero reinventa validación de schemas | Rechazado |

**Rationale**: PydanticAI se usa desde Slice 1 específicamente para **validación de outputs estructurados** contra el `output_schema` declarado en cada manifest. Su uso como runtime completo de agentes se evalúa en Slice 2 si el patrón de validación resulta sólido.

### Decision: LLM Abstraction — LiteLLM Detrás de Interfaz

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| LiteLLM detrás de interfaz `LLMProvider` | Provider-agnostic, cambiar proveedor sin cambios de código, mockeable para tests | ✅ ELEGIDO |
| LiteLLM directo en todo el código | Más simple pero locking a API de LiteLLM, difícil de testear sin red | Rechazado |

**Rationale**: `LLMProvider` (ABC) wrappea LiteLLM. La implementación concreta `LiteLLMProviderImpl` maneja selección de provider vía config. Permite mocks en tests y cambios de proveedor sin tocar código de agentes.

### Decision: Sandboxing — Controlled Trusted Plugin Execution para MVP

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| **Controlled trusted plugin execution** (manifest validation, interface contracts, execution limits, timeout, tool allowlist, structured output validation) | Suficiente para MVP sin overhead de subprocess/container | ✅ ELEGIDO |
| Subprocess/container sandboxing | Máxima seguridad pero overhead de desarrollo, debugging y deployment prematuro para MVP | Postergado |

**Rationale**: Para el MVP no se implementa sandbox fuerte. La ejecución controlada se basa en: validación de manifest (JSON Schema), contratos de interfaz (ABCs que el agente debe implementar), límites de ejecución (max_steps, max_tokens, timeout), tool allowlist (el agente solo accede a tools declaradas en su manifest), y validación de outputs estructurados (PydanticAI contra output_schema). Esto cubre los riesgos del MVP sin la complejidad de sandboxing por subprocess.

### Decision: AI ActorType — Constantes Propias de M4, Migración No Destructiva

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| **M4 define sus propias constantes AI** en `src/ai/domain/constants.py`. Migración no destructiva agrega `'agent'` al CHECK constraint de `audit_logs.actor_type` si es necesario | Sin acoplamiento a M3. Si `audit_logs` ya soporta `actor_type='agent'`, M4 solo escribe ese valor. Si no, migración `ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT ...` | ✅ ELEGIDO |
| M4 importa y extiende `ActorType` de M3 | Acoplamiento directo, M4 no puede evolucionar independientemente de M3 | Rechazado |

**Rationale**: `src/ai/domain/constants.py` define `AiActorType` (o reusa el enum de M3 por copia de valor, no por import). La migración 004 incluye `ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS ... ADD CONSTRAINT ... CHECK (actor_type IN ('system', 'user', 'agent'))` sólamente si el CHECK actual no lo permite. Es no destructiva.

### Decision: Reference Agents — Solo Fixtures para Validar Runtime

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| **Reference agents como fixtures de testing y validación de contratos** | Validan runtime, tests y contratos sin lógica de dominio. Claramente documentados como `type: reference` | ✅ ELEGIDO |
| Reference agents con lógica de dominio incipiente | Tentador pero rompe el out-of-scope de agentes especializados, riesgo de scope creep | Rechazado |

**Rationale**: Los reference agents existen únicamente para validar que el runtime carga manifests, ejecuta agentes, respeta límites y produce outputs válidos. No implementan lógica de dominio (no clasifican riesgo, no calculan indicadores). Su manifest incluye `type: reference` para que el runtime los identifique como no productivos.

## Data Flow

### Flujo Principal: Query → Orchestrator coordina Context Engine y State Manager

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Client    │ ──→ │   LangGraph      │ ──→ │   Agent         │
│  (Query)    │     │   Orchestrator   │     │   Runtime       │
└─────────────┘     └──────────────────┘     └─────────────────┘
                           │                           │
              ┌────────────┴────────────┐              │
              │                         │              │
              ↓                         ↓              │
     ┌────────────────┐     ┌──────────────────┐      │
     │  Context       │     │  State Manager   │      │
     │  Engine        │     │  (ai_workflow_   │      │
     │  (lee M3)      │     │   states /        │      │
     └────────────────┘     │   traces)        │      │
              │             └──────────────────┘      │
              │                         │              │
              ↓                         ↓              ↓
     ┌────────────────┐     ┌────────────────┐ ┌──────────────┐
     │   M3 Tables    │     │  audit_logs    │ │  Tool Layer  │
     │  (read-only)   │     │  (eventos AI)  │ │(M2/M3 wrappers)
     └────────────────┘     └────────────────┘ └──────────────┘
                                                       │
                                                       ↓
                                              ┌─────────────────┐
                                              │   Response      │
                                              │   Consolidation │
                                              └─────────────────┘
                                                       │
                                                       ↓
                                                ┌─────────────┐
                                                │   Client    │
                                                │ (Response)  │
                                                └─────────────┘
```

### Diagrama de Secuencia: Orchestrator coordina Context Engine y State Manager

```
Client          LangGraph         Agent Runtime     Context Engine     State Manager     Tool Layer     audit_logs
  │             Orchestrator           │                  │                 │                │              │
  │── query ──→                        │                  │                 │                │              │
  │                                    │                  │                 │                │              │
  │             │── build_context ────────────────────────>│                │                │              │
  │             │                     │                  │── read M3 ──>   │                │              │
  │             │                     │                  │<─ context JSON  │                │              │
  │             │<─ context ──────────────────────────────│                 │                │              │
  │                                    │                  │                 │                │              │
  │             │── init_state ───────────────────────────────────────────>│                │              │
  │             │<─ state_id ──────────────────────────────────────────────│                │              │
  │                                    │                  │                 │                │              │
  │             │── execute_step ────>│                  │                 │                │              │
  │             │                     │── tool_call ──────────────────────────────────────>│              │
  │             │                     │<─ tool_result ──────────────────────────────────────│              │
  │                                    │                  │                 │                │              │
  │             │── persist_trace ────────────────────────────────────────>│                │              │
  │             │<─ trace_id ───────────────────────────────────────────────│                │              │
  │                                    │                  │                 │                │              │
  │             │── audit_event ───────────────────────────────────────────────────────────────────────>│
  │                                    │                  │                 │                │              │
  │             │── consolidate ────> │                  │                 │                │              │
  │             │<─ final_result ──────│                  │                 │                │              │
  │<─ response ─│                     │                  │                 │                │              │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ai/__init__.py` | Create | Package init |
| `src/ai/domain/models.py` | Create | Dataclasses: WorkflowState, ExecutionTrace, AgentManifest, ToolResult, LLMRequest/Response |
| `src/ai/domain/interfaces.py` | Create | ABCs: LLMProvider, ContextEngine, StateManager, AgentRuntime, Tool, PromptTemplate |
| `src/ai/domain/constants.py` | Create | Enums AI propios: WorkflowStatus, AiActorType, ToolType |
| `src/ai/domain/errors.py` | Create | Exceptions: AgentExecutionError, ManifestValidationError, ToolExecutionError, ContextError |
| `src/ai/application/orchestrator.py` | Create | LangGraph orchestrator: workflow definition, state machine, step orchestration |
| `src/ai/application/response_consolidator.py` | Create | Merge de outputs multiagente estructurados |
| `src/ai/infrastructure/llm/litellm_provider.py` | Create | Implementación de LLMProvider vía LiteLLM |
| `src/ai/infrastructure/context/context_engine.py` | Create | Construcción de contexto desde tablas M3 |
| `src/ai/infrastructure/state/state_manager.py` | Create | Persistencia PostgreSQL de workflow states y traces |
| `src/ai/infrastructure/runtime/agent_runtime.py` | Create | Carga de agentes vía manifest, execution limits, validación de outputs |
| `src/ai/infrastructure/runtime/plugin_system.py` | Create | Agent discovery, manifest validation, registration |
| `src/ai/infrastructure/tools/geospatial_tools.py` | Create | Wrappers: RegionQueryTool, IndicatorLookupTool, RiskAssessmentTool |
| `src/ai/infrastructure/tools/llm_tools.py` | Create | Herramientas LLM: SummarizationTool, StructuredOutputTool |
| `src/ai/infrastructure/prompts/prompt_manager.py` | Create | Carga de prompts desde archivos versionados, metadata en tabla |
| `src/ai/infrastructure/observability/tracing.py` | Create | OpenTelemetry spans para workflows |
| `src/ai/infrastructure/observability/audit_logger.py` | Create | Escritura de eventos AI en audit_logs |
| `src/ai/agents/reference_agent/manifest.yaml` | Create | Manifest de reference agent (type: reference) |
| `src/ai/agents/reference_agent/agent.py` | Create | Reference agent mínimo para validar runtime |
| `migrations/004_ai_foundation.sql` | Create | Tablas: ai_workflow_states, ai_execution_traces, ai_prompt_metadata. Migración no destructiva a audit_logs si necesita actor_type='agent' |
| `tests/ai/` | Create | Tests de M4 |
| `requirements.txt` | Modify | Agregar: litellm, langgraph, pydantic-ai, opentelemetry-api, opentelemetry-sdk |

## Interfaces / Contracts

### LLMProvider (ABC)
```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute LLM completion. LiteLLM implementation behind this."""
        pass

    @abstractmethod
    def set_provider(self, provider: str) -> None:
        """Switch provider (openai, claude, gemini, azure)."""
        pass
```

### ContextEngine (ABC)
```python
class ContextEngine(ABC):
    @abstractmethod
    def build_context(self, region_ids: list[int],
                      indicator_codes: list[str] | None = None) -> dict:
        """Build structured JSON context from M3 tables (read-only)."""
        pass

    @abstractmethod
    def summarize_context(self, context: dict, max_tokens: int) -> str:
        """Truncate/summarize context to fit token window."""
        pass
```

### StateManager (ABC)
```python
class StateManager(ABC):
    @abstractmethod
    def create_state(self, workflow_id: str, initial_state: dict) -> int:
        """Create initial workflow state, return state_id."""
        pass

    @abstractmethod
    def update_state(self, state_id: int, state: dict) -> None:
        """Update workflow state (not audit_logs — separate table)."""
        pass

    @abstractmethod
    def persist_trace(self, state_id: int, step: str,
                      action: str, result: Any) -> int:
        """Persist execution trace, return trace_id."""
        pass
```

### AgentRuntime (ABC)
```python
class AgentRuntime(ABC):
    @abstractmethod
    def load_agent(self, manifest_path: Path) -> Any:
        """Load agent from validated manifest. Controlled trusted import."""
        pass

    @abstractmethod
    def execute(self, agent: Any, context: dict,
                limits: ExecutionLimits) -> AgentResult:
        """Execute agent with limits enforcement (timeout, max_steps, allowlist)."""
        pass

    @abstractmethod
    def validate_output(self, output: Any, schema: dict) -> bool:
        """Validate agent output against JSON Schema via PydanticAI."""
        pass
```

### Tool (ABC)
```python
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool identifier, must match manifest tool list."""
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute tool (wraps existing M2/M3 service)."""
        pass
```

## Testing Strategy

| Capa | Qué Testear | Approach |
|------|-------------|----------|
| Unit | LLMProvider mockeado, ContextEngine building, StateManager CRUD | pytest con repos mockeados, sin BD |
| Unit | Validación de manifest, validación de output schema | pytest con JSON Schema + PydanticAI |
| Integration | Workflow LangGraph, tool calls a repos M3 | pytest + Docker Compose PostgreSQL con datos M3 seedeados |
| Integration | LiteLLM provider switching, prompt template loading | pytest con HTTP mocked (responses library) |
| E2E | Workflow completo: query → context → agent → response | pytest + Docker Compose (PostgreSQL + M4), reference agent |
| E2E | State persistence, audit logs de eventos AI | Verificar filas en BD tras ejecución de workflow |

**Fixtures de test**:
- Mock LLMProvider con respuestas determinísticas
- Tablas M3 pre-seedeadas (regions, indicators, processed_layers)
- Reference agent con comportamiento conocido (`type: reference`)
- Docker Compose para tests de integración (mismo patrón que M1-M3)

## Migration / Rollout

### Slice 1 — Foundation
**Migration**: `004_ai_foundation.sql` — tablas `ai_workflow_states`, `ai_execution_traces`, `ai_prompt_metadata`. Si `audit_logs.actor_type` no soporta `'agent'`, migración no destructiva del CHECK constraint.
**Deps**: `litellm>=1.40.0`, `pydantic-ai>=0.0.20`
**Rollout**:
1. Ejecutar migration
2. Deploy `src/ai/domain/`, `src/ai/infrastructure/llm/`, `src/ai/infrastructure/context/`, `src/ai/infrastructure/state/`
3. Reference agent + tests
4. Verify: Context Engine lee M3, State Manager persiste, LiteLLM completa con mock

### Slice 2 — Orchestration
**Migration**: Ninguna (usa tablas de Slice 1)
**Deps**: `langgraph>=0.2.0`
**Rollout**:
1. Deploy `src/ai/application/orchestrator.py`, `response_consolidator.py`
2. Deploy `src/ai/infrastructure/runtime/`, `src/ai/infrastructure/tools/`, `src/ai/infrastructure/prompts/`
3. Manifests de reference agents
4. Verify: LangGraph ejecuta workflow, tools llaman a M3, response consolidation funciona

### Slice 3 — Hardening
**Migration**: Ninguna (usa tablas existentes)
**Deps**: `opentelemetry-api`, `opentelemetry-sdk`
**Rollout**:
1. Deploy `src/ai/infrastructure/observability/`
2. Execution limits, timeouts, idempotency checks
3. Reference agents adicionales para edge cases
4. Verify: traces en telemetría, audit logs con eventos AI, límites enforceados

## Open Questions

- [ ] **Context window strategy**: ¿Truncación por tokens o summarización semántica? La ventana configurable está spec'ed, el algoritmo exacto se resuelve en implementación.
- [ ] **Multi-tenancy**: ¿Workflow states aislados por tenant/user o single namespace? Se resuelve cuando haya un caso de uso concreto.
- [ ] **Prompt versioning**: ¿Soporte para A/B testing (múltiples versiones activas)? Postergado hasta Slice 2/3.
- [ ] **Retry strategy**: ¿Exponential backoff con jitter para rate limits de LLM? Se define en implementación de LLMProvider.
