## Exploration: Risk Orchestrator (Módulo 5, Section 6)

### Current State

The Hydric-Environmental Orchestrator is fully implemented and verified. It produces `HydricEnvironmentalOutput` as a Python object (a `@dataclass` with `overall_hydric_condition`, `subagent_outputs`, `confidence_score`, etc.). This output is **not persisted to any queryable table** — only the individual `agent_executions` are stored via `StateManagerImpl.persist_agent_execution()`.

The `LangGraphOrchestrator` (M4) supports sequential multi-agent execution with pre-built context via the M5 guard pattern. The `ContextEngineImpl` reads from M3 tables (`regions`, `indicators`, `risk_assessments`, `processed_geospatial_layers`) via repository interfaces.

No `MasterOrchestrator` class exists. The current entry point is the area orchestrator's `execute()` method called directly.

### Affected Areas

- `src/ai/application/area_orchestrators/hydric_environmental/orchestrator.py` — pattern to follow; should NOT be modified
- `src/ai/domain/models.py` — needs new enums (`RiskLevel`, `ImpactSeverity`) and dataclasses (`RiskOutput`, `AffectedZone`, `ScenarioProjection`)
- `src/ai/domain/interfaces.py` — may need new interface for territorial data if not using ContextEngine
- `src/ai/infrastructure/state/state_manager.py` — may need `persist_orchestrator_output()` or equivalent
- `src/ai/infrastructure/context/context_engine.py` — needs extension to read territorial variables
- `migrations/` — needs new tables for territorial variables (land_use, population_density, critical_infrastructure) + orchestrator output table
- `src/geospatial/domain/models.py` — needs new domain models for territorial variables

---

### Approaches

#### 1. New AreaOrchestrator class (`RiskOrchestrator`) — RECOMMENDED

Create `src/ai/application/area_orchestrators/risk/orchestrator.py` following the exact same pattern as `HydricEnvironmentalOrchestrator`.

**Architecture**:
```
RiskOrchestrator.execute(region_ids, hydric_output, workflow_id?) → RiskOutput
  1. Pre-build context via ContextEngine (existing + territorial extensions)
  2. Enrich context with hydric_output fields
  3. Create 3 agent manifests (RiskClassification, TerritorialPrioritization, PredictiveScenarios)
  4. Call LangGraphOrchestrator.execute_workflow() with pre-built context
  5. Transform consolidated output → RiskOutput
  6. Persist agent executions
```

**Key question**: Where does `hydric_output` come from?
- **Option A (Recommended)**: `HydricEnvironmentalOutput` is passed in-memory from a new **MasterOrchestrator** that calls both HydricEnvironmental and Risk orchestrators.
- **Option B**: Store hydric output in a new `orchestrator_outputs` table (migration 007), and RiskOrchestrator reads it via repository.

Pros:
- ✅ Consistent with proven HydricEnvironmentalOrchestrator pattern
- ✅ No changes to existing orchestrator code
- ✅ Clean separation of concerns
- ✅ Each orchestrator independently testable and deployable
- ✅ LangGraph M5 guard pattern already supports pre-built context

Cons:
- ❌ Need to solve the in-memory data handoff problem (Option A vs B)
- ❌ 3 new agents to build (RiskClassification, TerritorialPrioritization, PredictiveScenarios)
- ❌ Territorial variables need new DB tables

Effort: **High** (new orchestrator + 3 agents + new tables + tests)

---

#### 2. Extension of HydricEnvironmentalOrchestrator

Add risk methods directly into `HydricEnvironmentalOrchestrator` or create a hybrid orchestrator.

Pros:
- ✅ Can access `HydricEnvironmentalOutput` fields directly at construction time
- ✅ No handoff problem — single call produces both outputs

Cons:
- ❌ **Violates SRP** — one class handles hydric AND risk analysis
- ❌ Breaks the area-orchestrator abstraction (one area per orchestrator)
- ❌ Hard to test, hard to extend, hard to maintain
- ❌ Would need to modify an already verified/archived module

Effort: **Low** (quick coupling) but **high future cost** (technical debt)

---

#### 3. LangGraph Subgraph in Master Orchestrator

Build a `MasterOrchestrator` that holds a LangGraph graph with two subgraphs: Hydric (existing) and Risk (new).

Pros:
- ✅ Elegant for complex multi-step pipelines
- ✅ LangGraph supports subgraphs natively (v0.2+)
- ✅ Natural data flow between subgraphs (HydricOutput → RiskInput)

Cons:
- ❌ **No MasterOrchestrator exists today** — this is a much larger architecture change
- ❌ Adds significant complexity for MVP
- ❌ Existing HydricEnvironmentalOrchestrator would need to be restructured as a subgraph
- ❌ LangGraph subgraph pattern not yet established in the codebase

Effort: **Very High** (new architecture pattern, restructure existing code, double the scope)

---

### Question-by-Question Analysis

#### Q1: Which architecture?

**Winner: Option (a) — new `RiskOrchestrator` class.**

The archived M5 report explicitly lists "Risk/Economic/Alerts orchestrators" as pending technical debt for "Módulo 6+" with the note "dependen de este módulo". The thin-coordinator pattern (ADR #1) is proven, and creating a new orchestrator follows the same structure without modifying verified code.

#### Q2: Where does HydricEnvironmentalOutput come from?

The `HydricEnvironmentalOutput` dataclass is returned by `HydricEnvironmentalOrchestrator.execute()` but is **not persisted** — only `agent_executions` are stored. Two solutions:

| Option | Description | Complexity |
|--------|-------------|------------|
| **A. In-memory pass from orchestrator caller** | Build a lightweight orchestrator dispatcher (not yet a full MasterOrchestrator) that calls Hydric → passes output to Risk | Low — no new tables |
| **B. New `orchestrator_outputs` table** | Store hydric outputs in a queryable table (region_id, orchestrator_area, output JSONB, workflow_id, created_at) | Medium — new migration + repo + model |

**Recommendation for MVP**: **Option A** — a simple `OrchestratorDispatcher` that calls `HydricEnvironmentalOrchestrator.execute()` then passes the result to `RiskOrchestrator.execute()`. This avoids database changes and keeps the MVP focused. Add Option B in a post-MVP iteration when persistence/auditability is needed.

#### Q3: Historical risk data from State Manager?

**Yes, partially.** The `risk_assessments` table in M3 (migration 003) has:
- `risk_type`: drought, flood, hydric_stress, agroenvironmental
- `risk_level`: low, medium, high, critical
- `risk_score`, `confidence`, `explanation`
- `temporal_start` / `temporal_end`

The `ai_workflow_states` table in M4 stores workflow context as JSONB (including the hydric analysis context).

**What's missing**: The `risk_assessments` table was designed for M3's deterministic algorithms, not for AI-generated risk assessments. For MVP, it's usable as read-only historical context. For a future iteration, you could track AI-generated risk assessments separately (e.g., a join or a new `ai_risk_assessments` table).

**Recommendation**: ContextEngine already reads `risk_assessments` via `RiskAssessmentRepository`. The Risk Classification agent can consume these via context. No new work needed here for MVP.

#### Q4: Territorial variables?

**No tables exist.** Territorial variables needed:
- **Land use**: Agricultural, urban, forest, wetland categories per zone
- **Population density**: Inhabitants/km² per region
- **Critical infrastructure**: Hospitals, dams, roads, water treatment plants

**Options**:

| Option | Description | Effort |
|--------|-------------|--------|
| **A. New M3 migration** | New tables: `land_use_zones`, `population_density`, `critical_infrastructure` | High — full ETL + repos + domain models |
| **B. Region metadata JSONB** | Add territorial data to `regions.metadata` JSONB field | Low — no new tables, but query limitations |
| **C. Config files** | Static YAML/JSON files per region loaded at bootstrap | Low — no DB, but not queryable |

**Recommendation for MVP**: **Option B** — store territorial variables in the existing `regions.metadata` JSONB column. This avoids new migrations, keeps the data in the same DB, and the ContextEngine already reads `regions`. When the variables become independently updatable (separate ingestion pipelines), promote to dedicated tables.

#### Q5: Scenario projections — deterministic or LLM?

**For MVP: Deterministic templates.** Same principle as the hydric agents (ADR #3 — template-based NL, no LLM calls).

Rule-based projection engine:
- Take current `risk_level`, `overall_hydric_condition`, `probability_score`
- Apply simple decay/worsening rules
  - `7 days`: same risk level (short-term inertia)
  - `30 days`: one level improvement if trend improving, same if stable, one level worse if worsening
  - `90 days`: two levels improvement if improving, one level if stable, critical if worsening
- Scenarios: probable (rules above), pessimistic (worsen by 1 level), optimistic (improve by 1 level)
- Confidence: derived from hydric confidence + trend confidence

The `natural_language_summary` for scenarios is a deterministic template: *"At 7 days, [level] risk is projected. At 30 days, [condition] may [improve/worsen] to [level]. At 90 days..."*

**LLM integration**: Post-MVP, use an LLM to generate richer scenario narratives when the PRD explicitly requires it or when deterministic output feels too generic.

---

### Recommendation

**New `RiskOrchestrator` class (Approach 1)** with:

1. **Architecture**: Follow `HydricEnvironmentalOrchestrator` pattern exactly — new class in `src/ai/application/area_orchestrators/risk/`
2. **Context handoff**: Simple in-memory `OrchestratorDispatcher` for MVP (Option A for Q2)
3. **Territorial variables**: Store in `regions.metadata` JSONB (Option B for Q4) — extend ContextEngine to extract and surface them
4. **Scenario projections**: Deterministic rule engine (no LLM) for MVP
5. **Historical risk**: Use existing `risk_assessments` table via ContextEngine (no new work)
6. **New domain models**: `RiskLevel`, `ImpactSeverity`, `RiskOutput`, `AffectedZone`, `ScenarioProjection` enums/dataclasses
7. **3 risk agents**: Each with its own `manifest.yaml`, `agent.py`, `schemas.py`, `prompts/templates.py`
8. **Persist**: Same `agent_executions` pattern via `StateManagerImpl`

### Risks

- **Context handoff dependency**: `RiskOrchestrator` needs `HydricEnvironmentalOutput` as input. If there's no orchestrator calling both in sequence, the risk orchestrator is unusable. Mitigated by building `OrchestratorDispatcher` as part of MVP.
- **Territorial data quality**: Storing in `regions.metadata` JSONB means no schema enforcement. Mitigated by Pydantic validation in the Risk Classification agent.
- **Duplicate risk assessment storage**: The `risk_assessments` table from M3 has overlapping concepts. Must clearly distinguish M3's deterministic assessments from M5's AI-driven assessments to avoid confusion.
- **Scenario accuracy**: Deterministic projections will be formulaic. Set user expectations that MVP scenarios are rough estimates, not ML-powered forecasts.

### Ready for Proposal

**Yes.** The exploration is complete. All 5 questions have clear answers with tradeoffs documented.

The orchestrator should proceed to `sdd-propose` with:

- Change name: `modulo-5-risk-orchestrator`
- Recommended artifact mode: `hybrid` (consistent with existing project convention)
- Named change folder: `modulo-5-risk-orchestrator`

### Key Dependencies for Proposal

Items the proposal must surface:

1. **SDD scope**: New `RiskOrchestrator` + 3 risk agents + `OrchestratorDispatcher` + territorial data schema + new domain models for risk
2. **Not in scope**: MasterOrchestrator, LLM for scenarios, separate DB tables for territorial variables, persistence of orchestrator outputs
3. **Slice candidates**:
   - Slice 1: Foundation — domain models, migration (territorial JSONB in metadata), `OrchestratorDispatcher` interface
   - Slice 2: Risk Classification agent (CL-001) — highest value, core logic
   - Slice 3: Territorial Prioritization agent (PR-001) — depends on CL-001 output
   - Slice 4: Predictive Scenarios agent (SC-001) — depends on CL-001 output
   - Slice 5: Integration — `RiskOrchestrator.execute()` + end-to-end tests
4. **Delivery strategy**: Likely 4-5 stacked PRs (similar to modulo-5-area-orchestrators-agents)
