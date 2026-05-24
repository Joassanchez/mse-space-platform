# PRD — Módulo 3: Almacenamiento Geoespacial Central

## 1. Descripción general

El Módulo 3 define e implementa la capa central de almacenamiento geoespacial del sistema. Su objetivo es organizar la persistencia común para que los datos generados por los módulos anteriores puedan ser reutilizados por el backend, dashboard, agentes de IA, reportes, alertas y futuros módulos analíticos.

Este módulo debe construirse sobre PostgreSQL + PostGIS, reutilizando la base ya generada por el Módulo 1 y el Módulo 2.

El Módulo 1 registra o ingesta datos crudos.  
El Módulo 2 transforma archivos SMAP HDF5 en capas GeoTIFF georreferenciadas y registra trazabilidad en PostgreSQL.  
El Módulo 3 extiende esa base para convertirla en un modelo geoespacial central, consistente y consultable.

## 2. Objetivo del módulo

Diseñar e implementar el modelo de almacenamiento geoespacial central del MVP, incorporando regiones de análisis, fuentes de datos, capas procesadas, indicadores, evaluaciones de riesgo, alertas, impacto económico y auditoría técnica.

El objetivo no es calcular todavía indicadores complejos ni generar alertas inteligentes, sino dejar la estructura persistente preparada para los próximos módulos.

## 3. Contexto previo

El sistema ya cuenta con módulos anteriores.

### Módulo 1 — Ingesta de datos

Debe existir una base de datos o registros asociados a archivos crudos descargados o registrados. El agente debe auditar el estado real del repositorio antes de modificar el modelo.

Entidades esperadas o relacionadas:

- raw_files
- registros de ingesta
- metadatos de archivos crudos
- paths de almacenamiento local
- trazabilidad básica de origen

### Módulo 2 — ETL Geoespacial SMAP

El sistema ya transforma archivos SMAP HDF5 en GeoTIFF.

Elementos existentes confirmados:

- Tabla o entidad `geospatial_processing_jobs`
- Tabla o entidad `processed_geospatial_layers`
- Relación con `raw_files`
- Procesamiento de variable `sm_surface`
- CRS EPSG:6933
- Resolución aproximada de 9 km
- Escritura de GeoTIFF en `data/processed/smap/sm_surface/YYYY/MM/...`
- Idempotencia por `raw_file_id`, `variable_name` y `processing_version`
- Estadísticas básicas del raster
- Tests unitarios e integración

El Módulo 3 no debe romper esta implementación.

## 4. Problema a resolver

Actualmente el sistema puede ingerir datos y procesar capas geoespaciales, pero todavía no cuenta con un modelo persistente integral que permita relacionar:

- regiones geográficas de análisis;
- fuentes de datos;
- archivos crudos;
- capas procesadas;
- indicadores derivados;
- evaluaciones de riesgo;
- alertas;
- impacto económico/productivo;
- auditoría técnica.

Sin este modelo central, el dashboard, los agentes de IA, los reportes y los módulos analíticos futuros no tienen una fuente común de consulta.

## 5. Alcance funcional

El módulo debe permitir:

1. Registrar regiones geográficas de análisis.
2. Registrar fuentes de datos utilizadas por el sistema.
3. Relacionar capas procesadas con fuentes de datos.
4. Mantener compatibilidad con los datos crudos y procesados ya existentes.
5. Persistir indicadores calculados en módulos futuros.
6. Persistir evaluaciones de riesgo asociadas a regiones e indicadores.
7. Persistir alertas asociadas a evaluaciones de riesgo.
8. Persistir estimaciones económicas/productivas asociadas al riesgo.
9. Registrar eventos técnicos en auditoría.
10. Dejar consultas base preparadas para backend, dashboard y agentes.

## 6. Alcance técnico

La base recomendada es:

- PostgreSQL
- PostGIS
- JSONB para metadata flexible
- Índices B-tree para búsquedas comunes
- Índices GIST para geometrías
- Claves foráneas para trazabilidad
- Constraints para estados y clasificaciones controladas

## 7. Entidades principales

### 7.1 regions

Representa zonas geográficas de análisis.

Puede modelar:

- provincia;
- municipio;
- departamento;
- cuenca hídrica;
- lote piloto;
- región de prueba;
- polígono definido por el usuario.

Campos sugeridos:

- id
- name
- region_type
- country
- province
- geometry
- bbox
- area_km2
- metadata
- is_active
- created_at
- updated_at

Requisitos:

- Debe usar geometría PostGIS.
- Debe soportar MultiPolygon en EPSG:4326.
- Debe tener índice espacial GIST.
- Debe permitir activar/desactivar regiones sin borrado físico.

### 7.2 data_sources

Representa fuentes de datos utilizadas.

Ejemplos:

- SMAP
- SAOCOM
- Sentinel-1
- Sentinel-2
- CHIRPS
- ERA5
- INTA
- CONAE
- SMN

Campos sugeridos:

- id
- code
- name
- source_type
- provider
- spatial_resolution_m
- temporal_resolution
- native_crs
- description
- metadata
- is_active
- created_at
- updated_at

Requisitos:

- `code` debe ser único.
- Debe existir una fuente inicial para SMAP.
- Debe permitir futuras fuentes satelitales, meteorológicas o institucionales.

### 7.3 raw_datasets / raw_files

El agente debe auditar el modelo existente antes de crear una nueva tabla.

Regla principal:

- Si `raw_files` ya existe y cumple la función de archivo crudo, debe reutilizarse.
- No se debe crear una tabla redundante sin justificación.
- Si se necesita agrupar archivos crudos por producto, fecha o corrida, puede proponerse `raw_datasets` como entidad lógica, pero solo si aporta valor real.

### 7.4 processed_layers / processed_geospatial_layers

El Módulo 2 ya implementó `processed_geospatial_layers`.

Regla principal:

- No se debe duplicar esta tabla.
- Se debe reutilizar como fuente oficial de capas procesadas.
- Si se requiere el nombre conceptual `processed_layers`, puede crearse una vista SQL.
- Renombrar la tabla solo debe proponerse si no rompe dependencias existentes.

Campos relevantes esperados:

- id
- raw_file_id
- processing_job_id
- data_source_id
- variable_name
- layer_type
- file_path
- file_format
- crs
- resolution_m
- bbox
- geometry
- temporal_start
- temporal_end
- min_value
- max_value
- mean_value
- nodata_value
- processing_version
- metadata
- created_at

El agente debe verificar qué campos ya existen y cuáles faltan.

### 7.5 indicators

Representa indicadores analíticos calculados sobre capas procesadas y regiones.

Ejemplos futuros:

- humedad media del suelo;
- humedad mínima;
- humedad máxima;
- anomalía de humedad;
- porcentaje de área seca;
- porcentaje de área húmeda;
- clasificación hídrica preliminar;
- tendencia temporal.

Campos sugeridos:

- id
- region_id
- processed_layer_id
- indicator_code
- indicator_name
- indicator_type
- value
- unit
- classification
- confidence
- calculation_method
- temporal_start
- temporal_end
- metadata
- created_at

Requisitos:

- Debe estar vinculado a una región.
- Debe estar vinculado a una capa procesada cuando corresponda.
- Debe permitir metadata flexible.
- No es responsabilidad de este módulo calcular indicadores complejos.

### 7.6 risk_assessments

Representa evaluaciones de riesgo derivadas de indicadores.

Tipos esperados:

- drought
- flood
- hydric_stress
- agroenvironmental

Niveles esperados:

- low
- medium
- high
- critical

Campos sugeridos:

- id
- region_id
- indicator_id
- risk_type
- risk_level
- risk_score
- confidence
- method
- explanation
- temporal_start
- temporal_end
- metadata
- created_at

Requisitos:

- Debe vincularse a una región.
- Puede vincularse a uno o más indicadores según el diseño final.
- Para el MVP, puede tener relación directa con un indicador principal.

### 7.7 alerts

Representa alertas generadas a partir de evaluaciones de riesgo.

Campos sugeridos:

- id
- region_id
- risk_assessment_id
- alert_type
- severity
- title
- message
- status
- issued_at
- resolved_at
- metadata
- created_at

Severidades esperadas:

- info
- warning
- severe
- critical

Estados esperados:

- active
- acknowledged
- resolved
- dismissed

Requisitos:

- Debe estar asociada a una evaluación de riesgo.
- No debe implementar notificaciones externas en este módulo.
- Solo debe persistir la alerta.

### 7.8 economic_impacts

Representa estimaciones económicas o productivas asociadas a riesgos.

Campos sugeridos:

- id
- region_id
- risk_assessment_id
- impact_type
- estimated_loss_usd
- affected_area_ha
- crop_type
- yield_loss_percentage
- method
- assumptions
- confidence
- metadata
- created_at

Requisitos:

- Debe permitir guardar supuestos explícitos.
- Debe quedar preparada para futuros modelos económicos.
- No es obligatorio implementar cálculo económico sofisticado en este módulo.

### 7.9 processing_jobs

El Módulo 2 ya implementó `geospatial_processing_jobs`.

Regla principal:

- No se debe duplicar.
- Debe reutilizarse y extenderse solo si hace falta.
- Debe permitir registrar tipos futuros de procesamiento.

Tipos esperados:

- ingestion
- etl_smap
- indicator_calculation
- risk_assessment
- alert_generation
- economic_impact_estimation

### 7.10 audit_logs

Representa trazabilidad técnica transversal.

Campos sugeridos:

- id
- entity_type
- entity_id
- action
- actor_type
- actor_id
- message
- metadata
- created_at

Ejemplos:

- processed_layer created
- indicator created
- risk_assessment generated
- alert generated
- processing_job failed

Requisitos:

- Debe permitir auditoría técnica.
- Debe usar JSONB para metadata adicional.
- Debe poder registrar eventos del sistema sin depender de usuarios humanos.

## 8. Relación conceptual corregida

El modelo no debe asumir que `DataSource` depende de `Region`.

Modelo recomendado:

```text
DataSource
  └── RawFile / RawDataset
        └── ProcessedGeospatialLayer
              └── Indicator
                    └── RiskAssessment
                          ├── Alert
                          └── EconomicImpact

Region
  ├── Indicator
  ├── RiskAssessment
  ├── Alert
  └── EconomicImpact

La región representa el área de análisis.
La fuente representa el origen de datos.
Ambas dimensiones se cruzan a través de capas, indicadores y evaluaciones.

9. Requisitos funcionales
RF-01 — Gestión de regiones

El sistema debe permitir persistir regiones geográficas con geometría PostGIS, metadata y estado activo/inactivo.

RF-02 — Gestión de fuentes de datos

El sistema debe permitir persistir fuentes de datos con código único, proveedor, resolución, CRS nativo y metadata.

RF-03 — Compatibilidad con capas procesadas

El sistema debe reutilizar processed_geospatial_layers como tabla oficial de capas procesadas, extendiéndola solo si hace falta.

RF-04 — Relación entre capas y fuentes

Cada capa procesada debe poder relacionarse con una fuente de datos.

RF-05 — Persistencia de indicadores

El sistema debe permitir guardar indicadores asociados a regiones y capas procesadas.

RF-06 — Persistencia de evaluaciones de riesgo

El sistema debe permitir guardar evaluaciones de riesgo asociadas a regiones e indicadores.

RF-07 — Persistencia de alertas

El sistema debe permitir guardar alertas asociadas a evaluaciones de riesgo.

RF-08 — Persistencia de impactos económicos

El sistema debe permitir guardar estimaciones de impacto económico o productivo asociadas a riesgos.

RF-09 — Auditoría técnica

El sistema debe permitir registrar eventos técnicos relevantes en audit_logs.

RF-10 — Seeds mínimos

El sistema debe incluir datos iniciales mínimos para:

fuente SMAP;
una región piloto;
opcionalmente tipos o constantes necesarias.
10. Requisitos no funcionales
RNF-01 — Compatibilidad

El módulo no debe romper Módulo 1 ni Módulo 2.

RNF-02 — Idempotencia

Las migraciones y seeds deben poder ejecutarse sin duplicar información crítica.

RNF-03 — Trazabilidad

Toda entidad analítica debe mantener relación con su origen de datos cuando corresponda.

RNF-04 — Extensibilidad

El modelo debe permitir incorporar nuevas fuentes, regiones, indicadores y riesgos sin rediseñar la base.

RNF-05 — Integridad referencial

Deben utilizarse claves foráneas, constraints e índices adecuados.

RNF-06 — Consulta geoespacial

Las regiones y geometrías relevantes deben tener índices espaciales GIST.

RNF-07 — Metadata flexible

Las entidades principales deben soportar metadata mediante JSONB.

11. Fuera de alcance

Este módulo no debe implementar:

descarga de nuevos datos;
procesamiento HDF5;
cálculo real de indicadores complejos;
modelos predictivos;
agentes de IA;
dashboard;
APIs públicas complejas;
envío de notificaciones;
cálculo económico avanzado;
automatización completa de alertas.
12. Migraciones esperadas

El agente debe decidir si conviene una única migración o varias.

Opción simple para MVP:

003_create_geospatial_storage_model.sql

Debe incluir:

CREATE EXTENSION IF NOT EXISTS postgis
creación de tablas nuevas;
extensión segura de tablas existentes si hace falta;
claves foráneas;
índices;
constraints;
seeds mínimos o scripts de seed separados.
13. Estructura técnica sugerida

El agente debe respetar la arquitectura existente.

Estructura sugerida:

src/geospatial/
  domain/
    storage_models.py
    storage_interfaces.py

  infrastructure/
    persistence/
      postgres_repositories.py

Si el archivo de repositorios ya existe y está creciendo demasiado, puede dividirse en:

region_repository.py
data_source_repository.py
indicator_repository.py
risk_assessment_repository.py
alert_repository.py
economic_impact_repository.py
audit_log_repository.py

La decisión debe justificarse en el diseño SDD.

14. Tests esperados

El módulo debe incluir tests para verificar:

PostGIS está habilitado.
Se puede crear una región con geometría válida.
No se aceptan tipos inválidos cuando existan constraints.
Se puede crear la fuente SMAP.
data_sources.code es único.
processed_geospatial_layers puede vincularse con data_sources.
Se puede crear un indicador asociado a región y capa.
Se puede crear una evaluación de riesgo asociada a indicador.
Se puede crear una alerta asociada a riesgo.
Se puede crear un impacto económico asociado a riesgo.
Se puede registrar un audit log.
Existen índices espaciales.
Las claves foráneas impiden registros huérfanos.
Los seeds son idempotentes.
15. Criterios de aceptación

El módulo se considera terminado cuando:

PostgreSQL tiene PostGIS habilitado.
Existen las entidades centrales nuevas.
Las tablas existentes de M1/M2 no fueron duplicadas innecesariamente.
processed_geospatial_layers se integra con data_sources.
Existe una región piloto.
Existe una fuente SMAP.
Se pueden persistir indicadores, riesgos, alertas e impactos.
Existe auditoría técnica.
Los tests pasan.
La documentación SDD/OpenSpec queda actualizada.
Se genera verify-report.
El cambio queda archivado en OpenSpec si corresponde.
16. Decisión arquitectónica principal

La decisión principal del módulo es no crear un almacenamiento paralelo.

El Módulo 3 debe extender el almacenamiento existente de M1 y M2 hasta convertirlo en el modelo geoespacial central del sistema.

La fuente común de datos debe quedar preparada para:

backend;
dashboard;
agentes de IA;
reportes;
alertas;
módulos analíticos futuros.
17. Resultado esperado

Al finalizar el Módulo 3, el sistema debe contar con una base geoespacial central capaz de sostener el flujo:

Módulo 1
raw_files

Módulo 2
geospatial_processing_jobs
processed_geospatial_layers

Módulo 3
regions
data_sources
indicators
risk_assessments
alerts
economic_impacts
audit_logs

Este módulo deja preparado el terreno para el siguiente paso: cálculo de indicadores hídrico-ambientales sobre regiones usando las capas SMAP procesadas.