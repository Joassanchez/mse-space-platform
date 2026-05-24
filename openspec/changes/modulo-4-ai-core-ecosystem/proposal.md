# Proposal: Módulo 4 — AI Core Ecosystem

## Intent

Construir una capa cognitiva de IA sobre el pipeline determinístico M1-M3. M4 consume los outputs geoespaciales ya producidos (processed_layers, regions, indicators, risks, alerts) y provee infraestructura base para razonamiento multiagente. No contradice la decisión de M2 — esa restricción aplicaba al pipeline ETL, que sigue siendo determinístico. M4 es una capa cognitiva separada que corre por encima.

## Scope

### In Scope
- **Context Engine**: Consume processed_layers + regions + indicators, genera contexto estructurado para agentes
- **State Manager**: Persiste trazas de ejecución de workflows multiagente en PostgreSQL
- **Master Orchestrator**: LangGraph, coordinación de workflows de agentes
- **Agent Runtime**: Ejecución controlada de agentes con validación de manifest, contratos de interfaz, límites de ejecución y validación de outputs estructurados
- **Plugin System**: Registro dinámico de agentes mediante manifest declarativo
- **Tool Layer**: Wrapper sobre servicios geoespaciales existentes + herramientas nuevas para agentes
- **LLM Abstraction**: LiteLLM, abstracción provider-agnostic (OpenAI, Claude, Gemini, Azure)
- **Prompt Management**: Templates versionables, system prompt maestro, inyección contextual
- **Response Consolidation**: Fusión de outputs multiagente estructurados
- **Observability**: Logs, traces, métricas y auditoría extendida sobre audit_logs existente
- **Reference agents**: Agentes dummy/mock/example para validar el runtime, sin lógica de dominio especializada

### Out of Scope
- Agentes especializados de dominio (sequía, riesgo, impacto económico, etc.)
- Dashboards finales para usuarios
- Modelos predictivos complejos o entrenamiento ML
- Fine-tuning de modelos LLM
- Streaming en tiempo real
- Reemplazo o modificación del pipeline M1-M3
- Procesamiento multi-modal (imagen/audio)

## Capabilities

### New Capabilities
- `ai-context-engine`: Construcción de contexto estructurado desde outputs geoespaciales existentes
- `ai-agent-runtime`: Ejecución controlada de agentes con plugin system y manifest validation
- `ai-llm-abstraction`: Abstracción provider-agnostic vía LiteLLM
- `ai-prompt-management`: Gestión centralizada de templates y prompts versionables
- `ai-observability`: Trazas, métricas y auditoría para workflows de IA

### Modified Capabilities
- `geospatial-orchestration`: Punto de integración para que M4 consuma outputs del pipeline ETL
- `geospatial-storage`: Tablas de estado para trazas de workflows multiagente
- `geospatial-audit`: Extensión con metadata de trazas de IA

## Approach

Tres slices incrementales. Cada slice produce infraestructura verificable, no agentes de dominio.

**Slice 1 — Foundation**: LiteLLM abstraction (interfaz + implementación base), Context Engine (lectura de processed_layers + regions, generación de contexto estructurado), State Manager (modelo de datos + persistencia básica de trazas), migrations iniciales, reference agent mínimo para validar el loop LLM → contexto → respuesta.

**Slice 2 — Orchestration**: LangGraph master orchestrator (workflow base con steps, branching, estado), Agent Runtime (carga de plugins vía manifest, execution limits, validación de outputs), Plugin System (registro, discovery, interface contracts), Tool Layer (wrappers sobre servicios geoespaciales existentes + herramientas LLM), Prompt Management (templates versionables, system prompt maestro), Response Consolidation (fusión de outputs estructurados).

**Slice 3 — Hardening**: Observability (traces distribuidos, métricas de ejecución, extensión de audit_logs), manejo de errores, límites de seguridad, timeouts, idempotencia en workflows, reference agents adicionales para validar edge cases, documentación de integración para futuros agentes de dominio.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai/` | New | Core AI ecosystem (orchestrator, context, runtime, tools, prompts) |
| *(rutas a confirmar contra estructura real)* | — | Las tablas de state_manager se definen en migraciones nuevas; los models de dominio en `src/geospatial/domain/` extendido |
| `openspec/specs/geospatial-orchestration` | Modified | Punto de integración M4 → M2 |
| `openspec/specs/geospatial-storage` | Modified | Tablas de estado para trazas multiagente |
| `openspec/specs/geospatial-audit` | Modified | Extensión con metadata de IA |
| `migrations/` | New | Migraciones para tablas de state_manager, prompts, execution traces |
| `requirements.txt` | Modified | langgraph, pydantic-ai, litellm |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM provider lock-in | Low | LiteLLM abstraction desde el slice 1 |
| Agent execution sin límites (loops, costos) | Medium | LangGraph step limits + timeouts + execution limits en runtime |
| Context window overflow con datos geoespaciales reales | High | Context Engine con summarización progresiva, ventana de datos configurable |
| Dependencias nuevas no probadas en el stack existente | Medium | Slice 1 acotado para validar LangGraph + LiteLLM antes de escalar |
| Carga de plugins insegura | Medium | Validación de manifest, interface contracts, execution limits, sin promesa de sandboxing fuerte |

## Rollback Plan

1. Deshabilitar M4 vía config flag (el orquestador principal no inicia)
2. M1-M3 siguen operando sin cambios — zero data loss
3. Revertir migraciones de tablas M4
4. Remover `src/ai/` si existe
5. Revertir cambios en requirements.txt

## Dependencies

- earthaccess (existente)
- langgraph>=0.2.0
- pydantic-ai>=0.0.20
- litellm>=1.40.0
- PostgreSQL 15 + PostGIS (existente)

## Success Criteria

- [ ] **Context Engine**: genera contexto estructurado desde processed_layers + regions + indicators existentes
- [ ] **State Manager**: persiste trazas básicas de ejecución de workflows en PostgreSQL
- [ ] **LangGraph Orchestrator**: ejecuta un workflow mínimo controlado (single agent, step con branching)
- [ ] **Agent Runtime**: carga un reference agent mediante manifest y ejecuta una consulta contra el Context Engine
- [ ] **LiteLLM**: queda encapsulado detrás de una interfaz provider-agnostic, verificable con mock
- [ ] **Prompt Management**: carga templates versionables y los inyecta en el runtime
- [ ] **Response Consolidation**: fusiona outputs estructurados de múltiples agentes en un resultado único
- [ ] **Observability**: registra logs, traces y auditoría básica de ejecución de workflows
- [ ] **M1-M3**: sin modificaciones en su lógica core — cero regresiones
