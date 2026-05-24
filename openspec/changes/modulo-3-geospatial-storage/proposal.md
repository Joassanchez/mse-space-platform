# Proposal: Módulo 3 — Almacenamiento Geoespacial Central

## Intent

Crear el modelo de almacenamiento geoespacial central que relaciona regiones, fuentes de datos, capas procesadas, indicadores, evaluaciones de riesgo, alertas e impactos económicos. Habilitar PostGIS en PostgreSQL para consultas espaciales y establecer la base de datos común para backend, dashboard, agentes de IA y módulos analíticos futuros.

## Scope

### In Scope
- Habilitar PostGIS en Docker (postgres:15-alpine → postgis:15-3.4-alpine) con validación de volumen existente
- Migración `003_create_geospatial_storage_model.sql`: tablas nuevas (regions, indicators, risk_assessments, alerts, economic_impacts, audit_logs), columna `footprint_geometry GEOMETRY(Polygon, 4326)` en `processed_geospatial_layers`, FKs, constraints, índices GIST/B-tree
- Modelos de dominio en `src/geospatial/domain/storage_models.py` para nuevas entidades
- Repositorios divididos por entidad en `src/geospatial/infrastructure/persistence/` (region, data_source, indicator, risk_assessment, alert, economic_impact, audit_log)
- Seeds: fuente SMAP actualizada, región piloto (Argentina/Chaco)
- Tests: PostGIS habilitado, geometrías válidas, FKs, índices espaciales, idempotencia de seeds
- Auditoría técnica transversal para todas las entidades analíticas

### Out of Scope
- Cálculo real de indicadores complejos (solo persistencia)
- Modelos predictivos o agentes de IA
- APIs públicas o endpoints HTTP
- Envío de notificaciones externas
- Cálculo económico avanzado (solo estructura de persistencia)
- Backfill obligatorio de `footprint_geometry` para datos existentes (opcional, no bloqueante)

## Capabilities

> Contract between proposal and specs phases.

### New Capabilities
- `geospatial-storage`: Persistencia de regiones, indicadores, evaluaciones de riesgo, alertas e impactos económicos con soporte PostGIS
- `geospatial-audit`: Auditoría técnica transversal para todas las entidades analíticas

### Modified Capabilities
- `geospatial-persistence`: Extender para incluir relación `processed_geospatial_layers.data_source_id` y columna `footprint_geometry` con CRS EPSG:4326
- `geospatial-orchestration`: Actualizar orquestador para registrar eventos en audit_logs durante el pipeline

## Approach

**Slice 1 — Infraestructura PostGIS + Migración + Modelos:**
1. Validar volumen Docker existente, cambiar imagen a `postgis:15-3.4-alpine`, ejecutar `CREATE EXTENSION IF NOT EXISTS postgis`
2. Migración única `003_create_geospatial_storage_model.sql` con tablas nuevas, extensión de `processed_geospatial_layers`, FKs, índices
3. Modelos de dominio en `storage_models.py` (dataclasses o Pydantic)
4. Tests básicos: PostGIS habilitado, creación de región con geometría, validación de constraints

**Slice 2 — Repositorios + Seeds + Tests Completos:**
1. Dividir repositorios por entidad (7 archivos nuevos)
2. Seeds idempotentes: SMAP source, región piloto Chaco
3. Tests de integración: FKs, índices espaciales, relaciones entre entidades
4. Auditoría: integrar audit_logs en orquestador existente

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `docker-compose.yaml` | Modified | Cambiar imagen `postgres:15-alpine` → `postgis:15-3.4-alpine` |
| `migrations/003_create_geospatial_storage_model.sql` | New | Migración completa: PostGIS, tablas nuevas, extensión de existentes, índices |
| `src/geospatial/domain/storage_models.py` | New | Modelos de dominio: Region, Indicator, RiskAssessment, Alert, EconomicImpact, AuditLog |
| `src/geospatial/domain/interfaces.py` | Modified | Interfaces de repositorios para nuevas entidades |
| `src/geospatial/infrastructure/persistence/region_repository.py` | New | Implementación concreta para Region |
| `src/geospatial/infrastructure/persistence/data_source_repository.py` | New | Implementación concreta para DataSource |
| `src/geospatial/infrastructure/persistence/indicator_repository.py` | New | Implementación concreta para Indicator |
| `src/geospatial/infrastructure/persistence/risk_assessment_repository.py` | New | Implementación concreta para RiskAssessment |
| `src/geospatial/infrastructure/persistence/alert_repository.py` | New | Implementación concreta para Alert |
| `src/geospatial/infrastructure/persistence/economic_impact_repository.py` | New | Implementación concreta para EconomicImpact |
| `src/geospatial/infrastructure/persistence/audit_log_repository.py` | New | Implementación concreta para AuditLog |
| `src/geospatial/infrastructure/persistence/postgres_repositories.py` | Modified | Posible refactor para importar repositorios divididos |
| `src/geospatial/application/orchestrator.py` | Modified | Registrar eventos en audit_logs durante el pipeline |
| `seeds/001_geospatial_storage_seeds.sql` | New | Seeds idempotentes: SMAP source, región piloto |
| `tests/geospatial/unit/test_storage_models.py` | New | Tests de modelos de dominio |
| `tests/geospatial/integration/test_postgis_storage.py` | New | Tests de integración PostGIS + nuevas tablas |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Cambio de imagen Docker rompe volumen PostgreSQL existente | Medium | Validar compatibilidad de volumen postgres:15 → postgis:15, backup antes de migrar, documentar rollback |
| `footprint_geometry` requiere backfill de datos existentes | Low | Backfill opcional y no bloqueante; datos existentes mantienen `bbox NUMERIC[]` funcional |
| División de repositorios rompe imports existentes | Low | Mantener imports en `postgres_repositories.py` que re-exporten clases de repositorios divididos |
| PostGIS no disponible en entorno de producción | Medium | Documentar dependencia PostGIS en README, validar en CI/CD |
| Migración 003 falla a mitad de ejecución | Medium | Usar transacción SQL única, validar con `BEGIN; COMMIT;`, testear en entorno local primero |

## Rollback Plan

1. **Docker**: Revertir `docker-compose.yaml` a `postgres:15-alpine`, levantar contenedor (volume compatible)
2. **Migración**: Ejecutar `DROP TABLE IF EXISTS audit_logs, economic_impacts, alerts, risk_assessments, indicators, regions CASCADE;`, luego `ALTER TABLE processed_geospatial_layers DROP COLUMN IF EXISTS footprint_geometry;`
3. **Código**: Revertir commits del cambio `modulo-3-geospatial-storage` vía `git revert`
4. **Datos**: Restaurar backup de PostgreSQL previo a migración (si existe)

## Dependencies

- Módulo 1 completado (tablas `raw_files`, `data_sources` existentes)
- Módulo 2 completado (tablas `geospatial_processing_jobs`, `processed_geospatial_layers` existentes)
- Docker y docker-compose disponibles
- PostgreSQL 15+ con soporte para extensiones

## Success Criteria

- [ ] PostgreSQL ejecutándose con imagen `postgis:15-3.4-alpine` y extensión `postgis` habilitada (`SELECT PostGIS_Version();` retorna versión)
- [ ] Migración 003 ejecutada sin errores, todas las tablas nuevas creadas con FKs y constraints
- [ ] Columna `footprint_geometry GEOMETRY(Polygon, 4326)` existe en `processed_geospatial_layers` con índice GIST
- [ ] Índices espaciales GIST creados en `regions.geometry` y `processed_geospatial_layers.footprint_geometry`
- [ ] Seeds ejecutados: fuente SMAP existe en `data_sources`, región piloto existe en `regions`
- [ ] Tests de integración pasan: creación de región, indicador, riesgo, alerta, impacto económico, audit log
- [ ] Repositorios divididos importan correctamente sin romper código existente
- [ ] Auditoría registra eventos del orquestador en `audit_logs`
- [ ] Documentación SDD actualizada: proposal.md, spec.md, design.md, tasks.md
