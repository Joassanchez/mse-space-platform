## Archive Report

**Change**: modulo-5-area-orchestrators-agents
**Archived**: 2026-05-24
**Verdict**: PASS
**Hardening applied**: 2026-05-24 (post-hoc: UUID migration + plugin structure alignment)

### Artifact IDs (Engram)
- proposal: #162
- spec: #163
- design: #164
- tasks: #165
- verify-report: #167
- bugfix-review: #170
- prd-alignment-improvements: #171
- archive-report: this document

### Specs Published (Main)
- `openspec/specs/area-orchestrators/spec.md` — NEW (7 requirements, 11 scenarios)
- `openspec/specs/hydric-environmental-agents/spec.md` — NEW (11 requirements, 15 scenarios)

### Summary
- **42 tasks** completed across 6 phases
- **6 stacked PRs**: Foundation → Orchestrator → SoilMoisture → Weather → Drought → Integration
- **149 new tests** (all pass)
- **534 total tests** (0 failures, 0 regressions)
- **0 critical/warning issues**
- **6 ADRs** followed (+2 hardening changes)

### Hardening Changes (post-archive, pre-merge)

**1. UUID migration (PRD §11 alignment)**
- Migration `006_agent_executions_uuid.sql`: SERIAL → UUID via pgcrypto `gen_random_uuid()`
- `state_manager.persist_agent_execution()` now returns `str` (UUID string)
- Idempotent: checks column type before migrating

**2. Plugin structure alignment (PRD §4.2)**
Per agent (`soil_moisture`, `weather`, `drought`):
- `prompts/templates.py` — NL templates extracted from inline code
- `tools/__init__.py` — delegates to M4's AgentRuntime tool registry
- `runtime/__init__.py` — reserved for agent-specific runtime config
- Existing: `manifest.yaml`, `schemas.py`, `agent.py`, `tests/`

### PRD Alignment Improvements (applied post-review)
- Pydantic validation via `Schema(**raw).model_dump()` in all 3 agents (§9.3)
- Recommendation in Soil Moisture NL output (dry → "monitorear riego", critical → "riego urgente")
- `spi_status` enum (`SpiStatus`) with D0-D4 USDM mapping in DroughtOutput
- Short-term projection in Drought NL (worsening → "2-4 semanas")
- `RAINFALL_7D`, `TEMP_AVG`, `HUMIDITY`, `WIND_SPEED` fields in WeatherAgent (§5.4.4)
- `region_ids` in `HydricEnvironmentalOutput` for multi-region support

### Files Modified (Source Code)
- `src/ai/application/orchestrator.py` — M5 guard in `_node_build_context`
- `src/ai/domain/models.py` — 6 enums + SpiStatus + 5 dataclasses + AgentExecutionRecord + region_ids
- `src/ai/infrastructure/state/state_manager.py` — `persist_agent_execution()` → UUID string

### Files Created (Source Code)
- `src/ai/application/area_orchestrators/__init__.py`
- `src/ai/application/area_orchestrators/hydric_environmental/__init__.py`
- `src/ai/application/area_orchestrators/hydric_environmental/orchestrator.py`
- `src/ai/agents/soil_moisture/` — manifest, agent, schemas, prompts/, tools/, runtime/
- `src/ai/agents/weather/` — manifest, agent, schemas, prompts/, tools/, runtime/
- `src/ai/agents/drought/` — manifest, agent, schemas, prompts/, tools/, runtime/
- `migrations/005_agent_executions.sql` (original) + `006_agent_executions_uuid.sql`

### Files Created (Tests)
- `tests/ai/unit/test_orchestrator_guard.py` — 5 tests
- `tests/ai/unit/test_hydric_orchestrator.py` — 35 tests
- `tests/ai/unit/test_soil_moisture_agent.py` — 34 tests
- `tests/ai/unit/test_weather_agent.py` — 35 tests
- `tests/ai/unit/test_drought_agent.py` — 51 tests

### Architecture Decisions Implemented
| ADR | Status | Notes |
|-----|--------|-------|
| #1 Thin coordinator pattern | ✅ | HydricEnvironmentalOrchestrator calls LangGraphOrchestrator |
| #2 New agent_executions table | ✅ | Migration 005 + 006 UUID, no FKs |
| #3 Template-based NL | ✅ | prompts/templates.py per agent |
| #4 Weighted confidence | ✅ | 4-factor formula, 20% degradation penalty |
| #5 Pydantic schemas + validation | ✅ | models.py + per-agent schemas.py + model_dump() at runtime |
| #6 Migration independence | ✅ | 005/006 independent, no FKs to M3/M4 |
| #7 UUID primary key | ✅ | Migration 006, pgcrypto gen_random_uuid() |
| #8 Plugin structure | ✅ | prompts/, tools/, runtime/ per agent (§4.2) |

### Deuda Técnica Pendiente
| Item | Impacto | Próximo módulo |
|------|---------|----------------|
| `agent_executions.id` como UUID (vs SERIAL original) | Medio — PRD exige UUID para distributed tracing | ✅ Resuelto en hardening |
| Plugin structure sin prompts/tools/runtime | Bajo — no bloquea funcionalidad | ✅ Resuelto en hardening |
| Flood Agent sin datos SAR | Bajo — diferido explícitamente | Módulo 7+ |
| Risk/Economic/Alerts orchestrators | Medio — dependen de este módulo | Módulo 6+ |
| PydanticAI no usado como framework agentes | Bajo — solo pydantic BaseModel | Evaluar en Risk module |
| GeoPandas + Rasterio no integrados en agents | Bajo — tools vía M4 runtime | Evaluar en Risk module |
| Sin LLM calls en agents (template-based) | Medio — NL es determinístico, no genera lenguaje variado | Evaluar cuando se necesite lenguaje más rico |

### Learning (for future modules)
- M4 backward-compatible guard pattern proven — reusable for Risk, Economic, Alerts
- Plugin structure (prompts/, tools/, runtime/) es extensible sin modificar agent.py central
- Template extractions a prompts/templates.py facilitan internacionalización futura
- Pydantic model_dump() en execute() atrapa violaciones de schema en desarrollo, no en producción
- UUID migration con pgcrypto es segura e idempotente incluso con datos existentes

### Next Recommended Module
**Módulo 6**: Risk Orchestrator — consumes HydricEnvironmentalOutput via State Manager, classifies risk levels, prioritizes zones, projects scenarios
