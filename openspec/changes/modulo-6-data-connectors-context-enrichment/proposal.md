# Proposal: Data Connectors & Context Enrichment

## Intent
Enable weather and socioeconomic context for Risk/Alerts orchestrators via normalized data connectors + ContextEngine extension. No orchestrator logic — pure data infrastructure.

## Scope
### In Scope
- `weather_snapshots` table (migration 007)
- `OpenWeatherConnector` with mock-based tests
- `WeatherSnapshotRepository` (PostgreSQL)
- ContextEngine extension: `build_enriched_context()`
- `IndecConnector` stub + seed socioeconomic demo data
- `src/weather/` domain module

### Out of Scope
- EconomicOrchestrator, AlertsOrchestrator — future
- Real API calls in tests — mocks only
- Insurance agent

## Capabilities
### New
- `weather-ingestion`: OpenWeatherConnector + weather_snapshots table + repository
- `socioeconomic-seeds`: Demo INDEC data marked as reference/test

### Modified
- `ai-context-engine`: New `build_enriched_context()` method for weather + socioeconomic data

## Approach
1. New `src/weather/` module (domain/models, domain/interfaces, infrastructure/repo)
2. `OpenWeatherConnector` in `src/weather/connectors/` — standalone class
3. `ContextEngine.build_enriched_context()` reads from weather + existing repos
4. `IndecConnector` stub + `seeds/003_socioeconomic_demo.sql`
5. All tests use mocks — no internet dependency

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `src/weather/` | New | Domain + infrastructure module |
| `src/ai/infrastructure/context/context_engine.py` | Modify | Add build_enriched_context() |
| `src/ai/domain/interfaces.py` | Modify | Add method to ContextEngine ABC |
| `migrations/007_weather_snapshots.sql` | New | weather_snapshots table |
| `seeds/003_socioeconomic_demo.sql` | New | Demo indicator data |
| `src/config/sources.yaml` | Modify | Add openweather, indec sources |

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Weather connector too coupled to BaseIngestionConnector | Low | Standalone class, not extending ABC |
| Test without real API misses integration issues | Medium | Manual smoke test documented |

## Success Criteria
- [ ] OpenWeatherConnector.fetch() returns parsed WeatherSnapshot with mock
- [ ] build_enriched_context() includes weather + socioeconomic data
- [ ] 007 migration idempotent, weather_snapshots table queryable
- [ ] All tests pass with mocks (0 internet calls)
- [ ] Demo data clearly marked as reference/test
