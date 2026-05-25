# **1\. Descripción General**

Este documento especifica los requisitos funcionales, arquitectura y criterios de aceptación de la capa de Backend del AI Core Ecosystem. Esta capa actúa como interfaz entre el motor de agentes (AI Core) y el Frontend de presentación, exponiendo los resultados de análisis, estados de jobs, capas geoespaciales y alertas producidas por los agentes especializados.

El Backend no ejecuta lógica de agentes ni procesamiento geoespacial. Su responsabilidad comienza cuando los agentes han completado su ejecución y los resultados están disponibles en el State Manager, y termina cuando esos resultados son servidos de forma eficiente, segura y estructurada al Frontend.

| Proyecto padre | AI Core Ecosystem — Motor de IA Multiagente Geoespacial |
| :---- | :---- |
| **Código interno** | BACKEND-API-001 |
| **Versión** | 1.0 — MVP |
| **Framework** | FastAPI \+ Python 3.11+ |
| **Modo de ejecución** | Híbrido: scheduled \+ on-demand |
| **Consumidores** | Frontend propio (dashboard interno) |
| **Auth MVP** | API Key estática — sin auth compleja en primera versión |
| **Base de datos** | PostgreSQL \+ PostGIS (compartida con AI Core) |
| **Geoespacial** | GeoJSON sobre HTTP · MVT tiles opcionales (Etapa 2\) |

# **2\. Posición en la Arquitectura General**

El Backend API Layer se ubica entre el AI Core y el Frontend. No modifica ni re-procesa datos; los expone con las transformaciones mínimas necesarias para su consumo eficiente:

* Módulo 1 (Ingesta SMAP)  →  data/raw

* Módulo 2 (ETL Geoespacial)  →  data/processed

* Context Engine  →  contextos normalizados

* Agentes Especializados  →  structured outputs \+ natural language

* State Manager / PostgreSQL+PostGIS  →  resultados persistidos

* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

* ▶  BACKEND API LAYER (este módulo)  ◀

* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

* Frontend Dashboard  →  consumidor final

  *El Backend NO accede a data/raw ni data/processed directamente. Consume exclusivamente lo que PostgreSQL+PostGIS expone como resultado de ejecuciones de agentes.*

# **3\. Objetivos del Módulo**

## **3.1 Objetivo General**

Implementar una API REST asíncrona con FastAPI que exponga, de manera eficiente y estructurada, los resultados de análisis de agentes, capas geoespaciales y alertas para consumo del Frontend dashboard.

## **3.2 Objetivos Específicos**

* Servir outputs estructurados de agentes con filtros por región, fecha y área.

* Exponer capas geoespaciales en formato GeoJSON para renderizado de mapas.

* Gestionar y exponer el estado de jobs (scheduled y on-demand).

* Proveer endpoints de alertas activas priorizadas por severidad.

* Permitir lanzar análisis on-demand sobre regiones específicas.

* Implementar WebSocket o SSE para notificación en tiempo real de jobs completados.

* Mantener separación total entre la lógica de IA y la capa de presentación.

# **4\. Principios de Diseño**

| Principio | Implementación en Backend |
| :---- | :---- |
| Read-heavy API | La mayoría de endpoints son GET. El Backend es principalmente una capa de lectura sobre resultados ya computados. |
| Async-first | Todos los endpoints usan async/await. Operaciones de DB con asyncpg o SQLAlchemy async. |
| No lógica de negocio | El Backend no transforma ni reinterpreta resultados de agentes. Sirve lo que está en DB. |
| Desacoplamiento total | El Backend no importa ni depende de módulos del AI Core. Comparte únicamente la base de datos. |
| Geoespacial liviano | Entrega GeoJSON para el MVP. MVT tiles para optimización en etapa posterior. |
| Contratos tipados | Todos los responses usan Pydantic schemas. Sin respuestas sin tipo. |
| Observabilidad | Cada request loguea región, endpoint, duración y status. Trazable con el AI Core. |

# **5\. Arquitectura Interna**

## **5.1 Estructura de proyecto**

backend/

├── main.py                    \# App FastAPI, lifespan, middleware

├── config.py                  \# Settings (pydantic-settings, .env)

├── dependencies.py            \# DB session, auth, shared deps

│

├── api/

│   ├── v1/

│   │   ├── router.py          \# Agrega todos los routers v1

│   │   ├── analysis.py        \# Endpoints de resultados de agentes

│   │   ├── alerts.py          \# Endpoints de alertas activas

│   │   ├── geo.py             \# Endpoints de capas geoespaciales

│   │   ├── jobs.py            \# Endpoints de jobs (estado \+ trigger)

│   │   └── regions.py         \# Endpoints de regiones configuradas

│

├── schemas/

│   ├── analysis.py            \# Pydantic response models agentes

│   ├── alerts.py              \# Pydantic response models alertas

│   ├── geo.py                 \# GeoJSON feature schemas

│   ├── jobs.py                \# Job status schemas

│   └── regions.py             \# Region schemas

│

├── services/

│   ├── analysis\_service.py    \# Queries a agent\_executions

│   ├── alert\_service.py       \# Queries a alerts table

│   ├── geo\_service.py         \# Queries PostGIS → GeoJSON

│   ├── job\_service.py         \# CRUD jobs \+ trigger on-demand

│   └── region\_service.py      \# Queries a regions table

│

├── db/

│   ├── session.py             \# AsyncSession factory

│   └── models.py             \# SQLAlchemy ORM models (read-only views)

│

├── core/

│   ├── auth.py                \# API Key middleware

│   ├── cache.py               \# Redis cache layer

│   └── ws\_manager.py          \# WebSocket connection manager

│

└── tests/

    ├── test\_analysis.py

    ├── test\_alerts.py

    └── test\_geo.py

## **5.2 Capas internas**

| Capa | Responsabilidad | No hace |
| :---- | :---- | :---- |
| api/ | Recibe requests, valida parámetros, llama al service, serializa response. | Lógica de negocio, queries directas a DB. |
| schemas/ | Define contratos de entrada/salida con Pydantic. | Transformar datos de agentes. |
| services/ | Ejecuta queries, aplica filtros, construye responses. | Modificar datos de agentes. |
| db/ | Provee sesión async y modelos ORM de solo lectura. | Escritura sobre tablas de agentes. |
| core/ | Auth, cache, WebSocket manager. | Nada relacionado con IA o geoespacial. |

# **6\. Especificación de Endpoints**

  *Todos los endpoints están bajo el prefijo /api/v1. Todos requieren header X-API-Key en MVP.*

## **6.1 Analysis — Resultados de Agentes**

| Método | Path | Descripción | Query Params |
| :---- | :---- | :---- | :---- |
| GET | /analysis/ | Lista de ejecuciones de agentes paginada. | region\_id, area, date\_from, date\_to, status, page, limit |
| GET | /analysis/{execution\_id} | Detalle completo de una ejecución: structured\_output \+ natural\_language. | — |
| GET | /analysis/latest/ | Última ejecución completada por área y región. | region\_id (req), area |
| GET | /analysis/summary/ | Resumen agregado: condición hídrica \+ riesgo \+ alertas activas. | region\_id (req), date |

### **Response: GET /analysis/latest/**

{ "execution\_id": "uuid", "area": "hydric\_environmental",

  "region\_id": "cordoba\_pilot", "timestamp": "2024-01-15T08:00:00Z",

  "overall\_condition": "stressed", "confidence\_score": 0.84,

  "natural\_language\_summary": "La región presenta estrés hídrico moderado...",

  "structured\_output": { "soil\_moisture\_status": "dry", ... },

  "data\_completeness": 0.92 }

## **6.2 Alerts — Alertas Activas**

| Método | Path | Descripción | Query Params |
| :---- | :---- | :---- | :---- |
| GET | /alerts/ | Lista de alertas activas ordenadas por severidad. | region\_id, severity, active\_only, page, limit |
| GET | /alerts/{alert\_id} | Detalle de una alerta: mensajes por audiencia \+ acciones recomendadas. | — |
| GET | /alerts/active/count/ | Conteo de alertas activas agrupadas por severidad. | region\_id |
| PATCH | /alerts/{alert\_id}/acknowledge/ | Marca alerta como vista (soft-state en Backend). | — |

### **Response: GET /alerts/**

{ "items": \[ { "alert\_id": "uuid", "severity": "high",

  "event\_type": "drought\_moderate", "region\_id": "cordoba\_pilot",

  "created\_at": "2024-01-15T08:00:00Z", "is\_active": true,

  "affected\_zones\_count": 3, "executive\_summary": "..." } \],

  "total": 12, "page": 1, "limit": 20 }

## **6.3 Geo — Capas Geoespaciales**

  *Todos los endpoints geo devuelven GeoJSON válido (FeatureCollection). El Frontend los consume directamente con Mapbox GL JS o Leaflet.*

| Método | Path | Descripción | Query Params |
| :---- | :---- | :---- | :---- |
| GET | /geo/regions/ | Polígonos de regiones configuradas con metadata básica. | active\_only |
| GET | /geo/soil-moisture/ | Capa de humedad del suelo. Features con propiedades: sm\_surface, sm\_rootzone, status. | region\_id, date |
| GET | /geo/risk-zones/ | Zonas clasificadas por nivel de riesgo. Features con: risk\_level, probability\_score. | region\_id, date, min\_risk |
| GET | /geo/alerts/ | Puntos/polígonos de alertas activas para visualización en mapa. | region\_id, severity |
| GET | /geo/flood-extent/ | Extensión de anegamiento detectado si disponible. | region\_id, date |

### **Response: GET /geo/soil-moisture/**

{ "type": "FeatureCollection",

  "metadata": { "date": "2024-01-15", "source": "SMAP/SPL4SMGP", "confidence": 0.84 },

  "features": \[ { "type": "Feature",

    "geometry": { "type": "Polygon", "coordinates": \[...\] },

    "properties": { "zone\_id": "z01", "sm\_surface": 0.31,

      "sm\_rootzone": 0.27, "status": "dry", "anomaly\_pct": \-38 } } \] }

## **6.4 Jobs — Gestión de Análisis**

  *Los jobs scheduled son creados por el scheduler del AI Core. Los on-demand son disparados desde este endpoint por el usuario del dashboard.*

| Método | Path | Descripción | Body / Params |
| :---- | :---- | :---- | :---- |
| GET | /jobs/ | Lista de jobs con estado. Filtrable. | status, region\_id, date\_from, date\_to |
| GET | /jobs/{job\_id} | Detalle y progreso de un job específico. | — |
| POST | /jobs/trigger/ | Dispara un análisis on-demand. | { region\_id, areas\[\], date\_from, date\_to } |
| GET | /jobs/{job\_id}/logs/ | Logs de ejecución del job para debugging. | — |

### **POST /jobs/trigger/ — Request**

{ "region\_id": "cordoba\_pilot",

  "areas": \["hydric\_environmental", "risk"\],

  "date\_from": "2024-01-01", "date\_to": "2024-01-15" }

### **POST /jobs/trigger/ — Response**

{ "job\_id": "uuid", "status": "pending",

  "region\_id": "cordoba\_pilot", "areas": \["hydric\_environmental", "risk"\],

  "created\_at": "2024-01-15T10:00:00Z",

  "estimated\_duration\_seconds": 120,

  "ws\_channel": "ws://backend/ws/jobs/uuid" }

## **6.5 Regions — Regiones Configuradas**

| Método | Path | Descripción | — |
| :---- | :---- | :---- | :---- |
| GET | /regions/ | Lista de regiones activas con bbox y metadata. |  |
| GET | /regions/{region\_id} | Detalle de región: bbox, área, fuentes de datos activas, último análisis. |  |

# **7\. Tiempo Real — WebSocket y SSE**

## **7.1 Objetivo**

El Frontend necesita saber cuándo un job on-demand completó su ejecución sin hacer polling. Se implementa un canal WebSocket liviano por job\_id, y SSE como alternativa para contextos donde WebSocket no es viable.

## **7.2 WebSocket — canal por job**

WS  /ws/jobs/{job\_id}

El Frontend se conecta inmediatamente después de recibir la respuesta del POST /jobs/trigger/. El Backend emite eventos de progreso hasta la finalización:

| Evento | Payload | Cuándo se emite |
| :---- | :---- | :---- |
| job.started | { job\_id, started\_at, areas\[\] } | El AI Core inicia la ejecución |
| job.progress | { job\_id, area, status, pct\_complete } | Cada agente completa su ejecución |
| job.completed | { job\_id, finished\_at, result\_url } | Todos los agentes completaron |
| job.failed | { job\_id, error\_message, failed\_at } | Error en la ejecución |

## **7.3 SSE — stream de alertas activas**

GET  /alerts/stream/   (Accept: text/event-stream)

Para el panel de alertas del dashboard. El Backend emite un evento SSE cada vez que una nueva alerta es insertada en la base de datos por los agentes, usando LISTEN/NOTIFY de PostgreSQL.

event: new\_alert

data: { "alert\_id": "uuid", "severity": "critical", "region\_id": "...", "event\_type": "..." }

# **8\. Estrategia de Cache**

El Backend es read-heavy. Los resultados de agentes cambian en ciclos de horas (scheduled). Un cache liviano con Redis reduce carga sobre PostGIS en endpoints geoespaciales y de análisis.

| Endpoint | TTL | Invalidación |
| :---- | :---- | :---- |
| GET /analysis/latest/ | 5 min | Automática al completar nuevo job para esa región |
| GET /analysis/summary/ | 5 min | Automática al completar nuevo job |
| GET /geo/soil-moisture/ | 10 min | Automática al completar ETL de nuevo ciclo SMAP |
| GET /geo/risk-zones/ | 10 min | Automática al completar Orquestador de Riesgo |
| GET /alerts/active/count/ | 1 min | Automática al insertar nueva alerta |
| GET /regions/ | 60 min | Manual (config no cambia frecuentemente) |

  *Cache Key pattern: {endpoint}:{region\_id}:{date\_param}. Invalidación por tag usando Redis keyspace notifications.*

# **9\. Autenticación — MVP**

Para el MVP con un único usuario administrador interno, se implementa API Key estática. El diseño debe permitir migrar a JWT \+ roles en una etapa posterior sin cambios en los endpoints.

## **9.1 Implementación**

* Header requerido en todos los endpoints: X-API-Key: \<key\>

* La API Key se define en variables de entorno: API\_KEY=\<valor\>

* Validación implementada como FastAPI Dependency, no como middleware global, para facilitar override en tests.

* Endpoints de health check (/health, /ready) excluidos de auth.

## **9.2 Migración futura (fuera de alcance MVP)**

* JWT con OAuth2 Password Flow.

* Roles: admin, analyst, viewer.

* El Dependency de auth es reemplazable sin modificar los routers.

# **10\. Modelo de Datos — Vistas de Lectura**

El Backend no crea tablas propias. Consume las tablas creadas por el AI Core (Módulos 1, 2 y Agentes) mediante SQLAlchemy ORM en modo lectura y vistas PostgreSQL para queries complejas.

## **10.1 Tablas consumidas (read-only)**

| Tabla | Módulo origen | Uso en Backend |
| :---- | :---- | :---- |
| agent\_executions | PRD Agentes | Endpoints /analysis/ — resultados de agentes |
| alerts | PRD Agentes | Endpoints /alerts/ — alertas activas |
| ingestion\_jobs | Módulo 1 | Endpoints /jobs/ — estado de ingesta |
| raw\_files | Módulo 1 | Referencia en job logs |
| regions | AI Core config | Endpoints /regions/ |
| geo\_layers (PostGIS) | Módulo 2 ETL | Endpoints /geo/ — capas GeoJSON |

## **10.2 Vista: v\_latest\_analysis\_by\_region**

CREATE VIEW v\_latest\_analysis\_by\_region AS

  SELECT DISTINCT ON (region\_id, orchestrator\_area)

    execution\_id, region\_id, orchestrator\_area,

    structured\_output, natural\_language\_output,

    confidence\_score, data\_completeness, finished\_at

  FROM agent\_executions

  WHERE status \= 'completed'

  ORDER BY region\_id, orchestrator\_area, finished\_at DESC;

## **10.3 Vista: v\_active\_alerts\_geo**

CREATE VIEW v\_active\_alerts\_geo AS

  SELECT a.alert\_id, a.severity, a.event\_type,

    a.region\_id, a.created\_at,

    ST\_AsGeoJSON(z.geom)::jsonb AS geometry

  FROM alerts a

  JOIN geo\_layers z ON z.zone\_id \= ANY(a.affected\_zone\_ids)

  WHERE a.is\_active \= true;

# **11\. Requisitos No Funcionales**

## **11.1 Performance**

* Endpoints GET de análisis y alertas: p95 \< 200ms con cache activo.

* Endpoints GeoJSON: p95 \< 500ms para polígonos \< 5MB. Para capas mayores, respuesta paginada o bbox filter obligatorio.

* WebSocket job updates: latencia \< 2s desde evento en DB hasta llegada al Frontend.

## **11.2 Observabilidad**

* Cada request loguea: endpoint, region\_id, duration\_ms, status\_code, cache\_hit.

* Structured logs en JSON compatible con el Observability Layer del AI Core.

* Health check en /health (liveness) y /ready (readiness — verifica DB \+ Redis).

## **11.3 Extensibilidad**

* Versionado de API: /api/v1/. Nuevas versiones no rompen contratos existentes.

* Nuevos endpoints de agentes (Económico-Productivo, Alertas Tempranas) se agregan como nuevos routers sin modificar los existentes.

* La capa de servicios es reemplazable por gRPC o similar en etapas futuras.

## **11.4 Seguridad básica**

* CORS configurado explícitamente para el origen del Frontend únicamente.

* Rate limiting: 60 req/min por IP en MVP.

* El Backend nunca expone credenciales, rutas de archivos internos ni stack traces en responses.

# **12\. Stack Técnico**

| Componente | Tecnología | Justificación |
| :---- | :---- | :---- |
| Framework | FastAPI 0.110+ | Async nativo, OpenAPI auto-generado, Pydantic integrado, natural con stack Python IA. |
| ORM / DB | SQLAlchemy 2.0 async \+ asyncpg | Async queries sobre PostgreSQL/PostGIS sin bloquear el event loop. |
| Validación | Pydantic v2 | Contratos tipados, reutiliza schemas del AI Core. |
| Cache | Redis 7 \+ redis-py async | TTL por endpoint, invalidación por tag, pub/sub para SSE. |
| WebSocket | FastAPI WebSocket nativo | Canal liviano por job\_id para notificación de completados. |
| SSE | fastapi-sse / StreamingResponse | Stream de alertas nuevas hacia el Frontend. |
| GeoJSON | GeoAlchemy2 \+ shapely | Conversión PostGIS → GeoJSON en servicios geo. |
| Config | pydantic-settings | Variables de entorno tipadas, compatible con Docker Compose. |
| Testing | pytest-asyncio \+ httpx | Tests async de endpoints con DB en memoria o fixture. |
| Contenedor | Docker \+ Docker Compose | Mismo compose que AI Core, servicio adicional. |

# **13\. Integración Docker Compose**

El Backend se agrega como un servicio adicional al Docker Compose existente del AI Core. Comparte la red interna y la instancia de PostgreSQL+PostGIS:

services:

  backend:

    build: ./backend

    ports:

      \- "8000:8000"

    environment:

      \- DATABASE\_URL=postgresql+asyncpg://user:pass@postgres:5432/geoai

      \- REDIS\_URL=redis://redis:6379/1

      \- API\_KEY=${BACKEND\_API\_KEY}

      \- ALLOWED\_ORIGINS=http://localhost:3000

    depends\_on:

      \- postgres

      \- redis

    networks:

      \- geoai\_network

  *El Backend no depende del AI Core como servicio. Depende únicamente de PostgreSQL y Redis. Esto garantiza que puede reiniciarse o redesplegarse independientemente.*

# **14\. Estrategia de Desarrollo — MVP Incremental**

| Etapa | Componentes | Prerrequisito | Criterio de avance |
| :---- | :---- | :---- | :---- |
| Etapa 1 | FastAPI base \+ DB connection \+ /health \+ /ready | PostgreSQL disponible | App levanta, conecta a DB, responde /health |
| Etapa 2 | Schemas Pydantic \+ /regions/ \+ /analysis/latest/ | agent\_executions con datos reales | Devuelve último análisis Hídrico-Ambiental |
| Etapa 3 | Endpoints /geo/ (soil-moisture, risk-zones) | PostGIS con capas procesadas | GeoJSON válido consumible por Mapbox/Leaflet |
| Etapa 4 | Endpoints /alerts/ \+ cache Redis | Alertas generadas por agentes | Alertas ordenadas por severidad con TTL |
| Etapa 5 | /jobs/trigger/ \+ WebSocket job updates | AI Core acepta jobs externos | On-demand funcional con notificación en tiempo real |
| Etapa 6 | SSE /alerts/stream/ \+ rate limiting \+ CORS prod | Frontend conectado | Stream de alertas en vivo en dashboard |

# **15\. Criterios de Aceptación — MVP**

## **15.1 Funcionales**

* GET /api/v1/analysis/latest/?region\_id=cordoba\_pilot devuelve el último análisis Hídrico-Ambiental con structured\_output y natural\_language\_summary.

* GET /api/v1/geo/soil-moisture/?region\_id=cordoba\_pilot devuelve un GeoJSON válido con propiedades sm\_surface, sm\_rootzone y status.

* GET /api/v1/alerts/?region\_id=cordoba\_pilot devuelve alertas activas ordenadas por severidad descendente.

* POST /api/v1/jobs/trigger/ crea un job on-demand y devuelve job\_id \+ ws\_channel.

* El WebSocket ws/jobs/{job\_id} emite job.completed cuando el AI Core termina la ejecución.

## **15.2 No Funcionales**

* Todos los endpoints GET responden en menos de 500ms en condiciones normales.

* Un request sin X-API-Key válido recibe 401 Unauthorized.

* El endpoint /health responde 200 OK cuando DB y Redis están disponibles.

* Los responses de /geo/ son GeoJSON válido verificable con geojsonlint.

* El Backend puede reiniciarse sin afectar el AI Core ni los datos almacenados.

## **15.3 Fuera de alcance — v1.0**

* JWT / roles de usuario.

* MVT vector tiles (optimización etapa 2).

* Endpoints de área Económico-Productivo (requieren agentes de esa área completados).

* Rate limiting avanzado por usuario.

* Exportación de reportes PDF desde el Backend.

