# ARGPLANT AI

**Motor Inteligente de Decisiones Agrícolas para la Pampa Húmeda**

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-blue)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📖 Índice

- [Descripción del Producto](#-descripción-del-producto)
- [Casos de Uso](#-casos-de-uso)
- [Arquitectura](#-arquitectura)
- [Módulos](#-módulos)
- [API Reference](#-api-reference)
- [Stack Tecnológico](#-stack-tecnológico)
- [Requisitos e Instalación](#-requisitos-e-instalación)
- [Uso](#-uso)
- [Endpoints de Ejemplo](#-endpoints-de-ejemplo)
- [Variables de Entorno](#-variables-de-entorno)
- [Desarrollo](#-desarrollo)
- [Roadmap](#-roadmap)

---

## Nuestra visión

Desde el equipo de **MSE-SPACE** entendemos que el verdadero desafío no radica únicamente en acceder a grandes volúmenes de información, sino en transformarlos en herramientas que permitan tomar mejores decisiones.

Con esa premisa desarrollamos una propuesta que evoluciona nuestra plataforma hacia un producto de mayor alcance, integrando fuentes de información abiertas, consolidadas y validadas por organismos y profesionales del sector agropecuario. El objetivo es construir una base de datos confiable, estandarizada y reutilizable que pueda ser consumida por múltiples soluciones.

Como demostración de su potencial, desarrollamos un caso de uso integral que valida las capacidades de la plataforma mediante un sistema de apoyo a la toma de decisiones asistido por Inteligencia Artificial. Este producto complementario transforma datos satelitales, climáticos, agronómicos y económicos en recomendaciones accionables para productores, ingenieros agrónomos e instituciones.

De esta manera, **ARGPLANT Data Access** se posiciona como el producto principal de la solución, mientras que el **Decision Intelligence Dashboard** representa una implementación concreta que demuestra cómo esa infraestructura de datos puede convertirse en inteligencia aplicada para el sector agropecuario.

## 🚜 Descripción del Producto

## ARGPLANT Data Access

**La plataforma de datos agrícolas que transforma información satelital en decisiones inteligentes.**

## El desafío

Cada campaña agrícola genera millones de datos provenientes de satélites, estaciones meteorológicas, organismos públicos y modelos agronómicos.

Sin embargo, estos datos se encuentran dispersos, utilizan distintos formatos y requieren conocimientos técnicos para ser interpretados.

El verdadero problema no es la falta de información.

Es la dificultad para acceder a ella de forma integrada, confiable y lista para generar valor.

Hoy un productor, un ingeniero agrónomo o una empresa AgTech deben consultar múltiples APIs, descargar imágenes satelitales, interpretar indicadores y desarrollar su propia infraestructura antes de poder tomar una decisión.

Eso implica tiempo, costos y una enorme barrera tecnológica.

## Nuestra propuesta

## ARGPLANT Data Access

ARGPLANT Data Access es una plataforma de integración de datos agrícolas que unifica información proveniente de múltiples fuentes abiertas en una única API estandarizada.

La plataforma abstrae la complejidad técnica de cada proveedor de datos y entrega información consistente, documentada y preparada para ser utilizada por cualquier aplicación.

Actualmente integra:

- NASA POWER
- Sentinel (Copernicus)
- SMAP
- MAGyP
- OpenWeather
- Modelos agronómicos INTA / FAO

Todo disponible mediante una API REST documentada con OpenAPI.

El objetivo es que cualquier desarrollador, empresa o institución pueda construir soluciones agrícolas sin tener que integrar individualmente cada fuente de información.

## Decision Intelligence Dashboard

Como demostración del potencial de ARGPLANT Data Access desarrollamos una aplicación de apoyo a la toma de decisiones basada en Inteligencia Artificial.

Este dashboard consume exclusivamente la información provista por Data Access y la transforma en conocimiento accionable para el productor.

La plataforma permite:

- visualizar el estado completo de un lote
- detectar anomalías antes de que sean visibles
- estimar riesgo productivo
- calcular impacto económico potencial
- generar alertas inteligentes
- recomendar acciones utilizando IA Generativa

En lugar de presentar únicamente indicadores técnicos, el sistema responde la pregunta que realmente necesita responder un productor:

> **¿Cuál es la mejor decisión que puedo tomar hoy para este lote?**

La Inteligencia Artificial interpreta el contexto completo utilizando información satelital, climática, agronómica y económica para generar recomendaciones claras, priorizadas y justificadas.

## Arquitectura del producto

ARGPLANT está compuesto por dos capas claramente diferenciadas.

## ARGPLANT Data Access

Producto principal.

Responsable de:

- integración de datos
- normalización
- estandarización
- acceso mediante API
- documentación OpenAPI
- escalabilidad
- reutilización por terceros

Puede comercializarse o utilizarse como plataforma independiente.

## Decision Intelligence

Producto construido sobre Data Access.

Responsable de:

- análisis agronómico
- motor de reglas
- modelos predictivos
- IA Generativa
- alertas inteligentes
- dashboard de monitoreo
- soporte a la toma de decisiones

Toda la inteligencia del sistema se alimenta exclusivamente desde ARGPLANT Data Access.

---

## 👥 Casos de Uso

| Para el Productor | Para el Ingeniero Agrónomo |
|-------------------|---------------------------|
| *"¿Qué hago hoy con el lote 123?"* | *"¿Cuál de mis 15 establecimientos necesita atención urgente?"* |
| Recibe una alerta en su celular: "Estrés hídrico en R4. Regar 25mm zona norte esta noche." | Ve el panel de visión con NDVI, humedad de suelo SMAP, datos técnicos y score de riesgo. |
| Conoce el impacto económico: "Si actuás ahora, protegés $9M ARS." | Respalda sus recomendaciones al productor con evidencia satelital y agronómica. |

| Para el Desarrollador | Para la Institución |
|-----------------------|---------------------|
| Una API REST documentada. Un solo endpoint (`/api/v1/analysis`) devuelve todo unificado. | Monitoreo regional: INTA, municipios, cooperativas pueden consumir datos agregados para toda una zona. |
| Feature flags por fuente: activá solo lo que tengas credenciales. | API gratuita, sin licencias. Datos de NASA, Copernicus y MAGyP. |

### Posibilidades de desarrollo flexible

ARGPLANT Data Service está diseñado como **plataforma**, no como producto cerrado. Sobre esta base de datos se pueden construir:

- **Dashboards de visión** — como el incluido en este repositorio, que muestra KPIs, alertas y mapa satelital.
- **Sistemas de alerta temprana** — con SSE (Server-Sent Events) para notificaciones en tiempo real al celular del productor.
- **Modelos predictivos personalizados** — el rule engine actual es extensible; puede reemplazarse por ML sin tocar la capa de datos.
- **Aplicaciones móviles** — la API devuelve JSON, CORS está habilitado, listo para cualquier frontend.
- **Integraciones con ERPs agrícolas** — los datos normalizados pueden alimentar sistemas de gestión de establecimientos.

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Dashboard)                         │
│                   http://localhost:8000/                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ GET /api/v1/analysis
                               │ POST /api/v1/predict
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ANALYSIS ORCHESTRATOR                            │
│              argplant/modules/analysis/orchestrator.py              │
│          asyncio.gather → 4 módulos en paralelo                    │
└────┬──────────────┬──────────────┬──────────────┬───────────────────┘
     │              │              │              │
     ▼              ▼              ▼              ▼
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│AGROCLIM │  │SATELLITE │  │ AGRONOMY │  │ ECONOMY  │
│NASA POWER│ │SMAP      │  │BBCH/Kc   │  │MAGyP     │
│OpenWeather│ │Sentinel  │  │INTA/FAO  │  │Precios   │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │              │              │              │
     └──────────────┴──────────────┴──────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       RULE ENGINE (Modelo)                          │
│                argplant/modules/model/engine.py                     │
│     Reglas agronómicas → Anomalías → Riesgo → Yield → Impacto      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     COMMUNICATION (Alertas)                         │
│          POST /alerts  ·  SSE Stream  ·  NOTIFY PostgreSQL         │
│          Gemini IA → Mensajes accionables en español               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Módulos

### 🌦️ Agroclimate
Fuentes: **NASA POWER** (parámetros agroclimáticos históricos) + **OpenWeather** (condiciones actuales y forecast).
- `GET /api/v1/agroclimate/weather?lat=&lon=`
- `GET /api/v1/agroclimate/power?lat=&lon=&start_date=&end_date=&parameters=`

### 🛰️ Satellite
Fuentes: **SMAP** (humedad de suelo vía NASA Earthdata) + **Sentinel-1/2** (SAR y óptico vía Copernicus CDSE).
- `GET /api/v1/satellite/smap?bbox=&start_date=&end_date=`
- `GET /api/v1/satellite/sentinel/search?platform=&bbox=&start=&end=&max_cloud=`
- `POST /api/v1/satellite/sentinel/{scene_id}/download`

### 🌱 Agronomy
Catálogos estáticos curados de **FAO-56** e **INTA**: etapas BBCH, coeficientes Kc, umbrales térmicos para soja y maíz.
- `GET /api/v1/agronomy/crops`
- `GET /api/v1/agronomy/crops/{id}/stages`

### 💰 Economy
Fuente: **MAGyP Monitor de Granos** — precios diarios de soja, maíz, trigo y girasol en puertos argentinos.
- `GET /api/v1/economy/prices?producto=&puerto=&desde=&hasta=`

### 🧠 Model (Prediction)
Motor de reglas agronómicas que evalúa el análisis unificado y genera:
- Anomalías (estrés hídrico, estrés térmico)
- Score de riesgo con factores ponderados
- Estimación de rinde y pérdida
- Impacto económico proyectado
- Recomendaciones accionables
- **`POST /api/v1/predict`**

### 🔗 Analysis (Orquestador)
Unifica los 4 módulos en una sola respuesta. Usa `asyncio.gather` para ejecución paralela con degradación graceful.
- **`GET /api/v1/analysis?lot_id=&crop=&lat=&lon=&date=`**

### 📡 Communication (Alertas + IA)
- **`POST /api/v1/alerts`** — crear alerta con deduplicación (ventana 8h)
- **`GET /api/v1/alerts/stream`** — SSE para tiempo real vía PostgreSQL `NOTIFY`
- **`POST /api/v1/chat`** — endpoint directo al LLM (Gemini por defecto, extensible a OpenAI)

---

## 📡 API Reference

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/analysis` | GET | **Análisis unificado** de los 4 módulos |
| `/api/v1/predict` | POST | Predicción: anomalías, riesgo, yield, economía |
| `/api/v1/agroclimate/weather` | GET | Clima actual (OpenWeather) |
| `/api/v1/agroclimate/power` | GET | Parámetros agroclimáticos (NASA POWER) |
| `/api/v1/satellite/smap` | GET | Catálogo SMAP |
| `/api/v1/satellite/sentinel/search` | GET | Catálogo Sentinel-1/2 |
| `/api/v1/satellite/sentinel/{id}/download` | POST | Descarga async de escena |
| `/api/v1/agronomy/crops` | GET | Lista de cultivos |
| `/api/v1/agronomy/crops/{id}/stages` | GET | Etapas BBCH del cultivo |
| `/api/v1/economy/prices` | GET | Precios de granos (MAGyP) |
| `/api/v1/alerts` | GET | Listar alertas activas |
| `/api/v1/alerts` | POST | Crear alerta |
| `/api/v1/alerts/stream` | GET | SSE — alertas en tiempo real |
| `/api/v1/chat` | POST | Chat directo con LLM |
| `/api/v1/jobs/{job_id}` | GET | Estado de job async |
| `/docs` | GET | Swagger UI interactiva |

---

## 💻 Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| API | FastAPI 0.115+ (async) |
| HTTP Client | httpx (async, connection pooling) |
| Base de Datos | PostgreSQL 16 + PostGIS |
| ORM | SQLAlchemy 2.0 (async) |
| Migraciones | Alembic |
| Cache | Redis 7 |
| Task Queue | arq (async + Redis) |
| LLM | Gemini 3.5 Flash Lite (extensible a OpenAI, Anthropic) |
| Frontend | Vanilla HTML/CSS/JS + Material Symbols |
| Contenedores | Docker + Docker Compose |
| Testing | pytest + pytest-asyncio + fakeredis |

---

## 🔧 Requisitos e Instalación

### Prerrequisitos

- [Docker](https://docs.docker.com/get-docker/) y Docker Compose
- Python 3.12+ (opcional, solo para desarrollo local sin Docker)
- API keys de servicios externos (ver [Variables de Entorno](#-variables-de-entorno))

### Clonar e instalar

```bash
git clone https://github.com/Joassanchez/mse-space-platform.git
cd mse-space-platform
git checkout feature/argplant-data-service-06-analysis-orchestrator

# Crear .env desde el template
cp .env.example .env

# Editar .env con tus API keys
# OPENWEATHER_API_KEY=...
# EARTHDATA_USERNAME=...
# GEMINI_API_KEY=...

# Construir y levantar
docker compose build
docker compose up -d

# Ejecutar migraciones
docker compose exec api alembic upgrade head
```

### Verificar

```bash
# Health check
curl http://localhost:8000/health

# Abrir dashboard
open http://localhost:8000/

# Abrir Swagger UI
open http://localhost:8000/docs
```

> **Nota para Windows**: Si la DB falla con "database files are incompatible", eliminá el volumen anterior: `docker compose down -v && docker compose up -d`

---

## 🚀 Uso

### Dashboard

Abrí `http://localhost:8000/` → el dashboard carga automáticamente datos de Pergamino. Hacé clic en **"Ingresar Datos"** para cambiar lote, cultivo, coordenadas y fecha.

### API — Un solo endpoint para el frontend

```bash
curl "http://localhost:8000/api/v1/analysis?lot_id=lote-123&crop=soy&lat=-33.9278607&lon=-60.567172&date=2026-07-21"
```

Devuelve datos unificados de los 4 módulos:

```json
{
  "query": { "lot_id": "lote-123", "crop": "soy", "lat": -33.9278, "lon": -60.5671, "date": "2026-07-21" },
  "agroclimate": { "current": { "temp": 25.3, "humidity": 55 }, "historical": { "precipitation_15d_mm": 10.4 } },
  "satellite": { "soil_moisture_value": { "soil_moisture": 0.32 }, "optical": [] },
  "agronomy": { "crop_info": { "name": "Soja" }, "current_stage": { "bbch_code": "75", "name": "Llenado de vainas" } },
  "economy": { "latest_price": { "promedio": 498851, "fecha": "2026-07-21" } },
  "meta": { "status": "complete", "missing_modules": [] }
}
```

### Predicción y recomendaciones

```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"lot_id":"lote-123","crop":"soy","lat":-33.9278607,"lon":-60.567172,"date":"2026-07-21"}'
```

### Alertas en tiempo real (SSE)

```bash
# Terminal 1: escuchar stream
curl -N http://localhost:8000/api/v1/alerts/stream

# Terminal 2: disparar predicción (genera alertas automáticamente)
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"lot_id":"lote-123","crop":"soy","lat":-33.9278,"lon":-60.5671,"date":"2026-07-21"}'
```

---

## 🔑 Variables de Entorno

Copiá `.env.example` a `.env` y completá las que necesites. Las fuentes se activan/desactivan con flags:

```ini
# ── API Keys ──────────────────────────
OPENWEATHER_API_KEY=        # https://home.openweathermap.org/api_keys
EARTHDATA_USERNAME=         # https://urs.earthdata.nasa.gov/
EARTHDATA_PASSWORD=
CDSE_USERNAME=              # https://identity.dataspace.copernicus.eu/
CDSE_PASSWORD=
GEMINI_API_KEY=             # https://aistudio.google.com/apikey

# ── Feature Flags (activar/desactivar fuentes) ──
ENABLE_OPENWEATHER=True
ENABLE_NASA_POWER=True
ENABLE_SMAP=True
ENABLE_SENTINEL=False       # ← CDSE tarda 24h en activarse
ENABLE_MAGYP=True

# ── LLM / IA ──────────────────────────
LLM_PROVIDER=gemini          # gemini | openai
LLM_MODEL=gemini-3.5-flash-lite

# ── Infra ─────────────────────────────
DATABASE_URL=postgresql+asyncpg://argplant:argplant@localhost:5432/argplant
REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60

# ── Pergamino (coordenadas default) ───
INGESTION_COORDS_LAT=-33.9278607
INGESTION_COORDS_LON=-60.567172
```

---

## 🧪 Desarrollo

### Tests

```bash
# Todos los tests
py -m pytest tests/ -v

# Solo un módulo
py -m pytest tests/unit/test_model_engine.py -v
py -m pytest tests/integration/test_analysis_router.py -v
```

### Lint

```bash
ruff check argplant/ tests/
ruff check --fix argplant/ tests/
```

### Docker sin build completo (desarrollo local)

```bash
# Solo DB + Redis
docker compose up -d db redis

# API en local con hot reload
pip install -e ".[dev]"
uvicorn argplant.main:app --reload --port 8000
```

---

## 🗺 Roadmap

| Estado | Ítem |
|--------|------|
| ✅ | Data Service — 4 módulos de ingesta de datos |
| ✅ | Analysis Orchestrator — endpoint unificado |
| ✅ | Rule Engine — detección de anomalías agronómicas |
| ✅ | Prediction — riesgo, yield, impacto económico |
| ✅ | Communication — alertas + SSE + PostgreSQL NOTIFY |
| ✅ | Dashboard — frontend vanilla con datos reales |
| ✅ | LLM Integration — Gemini (extensible a OpenAI) |
| ✅ | Feature Flags — activar/desactivar fuentes por .env |
| 🔲 | SAOCOM — satélite argentino (requiere acceso CONAE) |
| 🔲 | NDVI real desde Sentinel-2 (procesamiento de bandas) |
| 🔲 | Módulo de comunicación multicanal (email, WhatsApp) |
| 🔲 | App móvil PWA |
| 🔲 | Multi-lote — análisis simultáneo de varios establecimientos |
| 🔲 | Modelos ML — reemplazar rule engine con machine learning |

---

## 📄 Licencia

MIT © 2026
