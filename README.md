# 🌍 MSE-Space Platform

## Plataforma Inteligente de Gestión Hídrica y Riesgo Agroambiental

Repositorio oficial: https://github.com/Joassanchez/mse-space-platform.git

---

## 🛰️ Contexto del Proyecto

Este proyecto es desarrollado por el equipo **MSE-Space** en el marco del **Hackatón Argentina al Espacio**, dentro del desafío:

> **“El poder de los datos desde el espacio”**

La propuesta consiste en una plataforma técnica para integrar, procesar y analizar datos espaciales aplicados a la gestión hídrica, el monitoreo agroambiental y la anticipación de riesgos territoriales en Argentina.

El objetivo principal es transformar datos satelitales y fuentes complementarias en información geoespacial procesada, indicadores territoriales, evaluaciones de riesgo, alertas y análisis asistido por inteligencia artificial.

---

## 🎯 Objetivo

Diseñar y validar una arquitectura modular capaz de convertir datos espaciales heterogéneos en información útil para la toma de decisiones hídrico-agroambientales.

El sistema aborda casos como:

- Monitoreo de humedad del suelo.
- Detección de anegamientos e inundaciones.
- Seguimiento de sequías y estrés hídrico.
- Generación de indicadores territoriales.
- Clasificación de riesgo hídrico-agroambiental.
- Estimación de impacto económico potencial.
- Enriquecimiento del análisis mediante agentes de IA.

La plataforma se plantea como un **MVP técnico y validable**, no como una solución final completamente automatizada.

---

## 🧠 Enfoque Técnico

La arquitectura del sistema combina procesamiento determinístico e inteligencia artificial aplicada.

Los procesos críticos de adquisición, validación, reproyección, transformación, almacenamiento y generación de capas geoespaciales se implementan mediante pipelines controlados y reproducibles.

La inteligencia artificial se incorpora sobre datos ya procesados, principalmente para:

- Interpretar indicadores.
- Clasificar niveles de riesgo.
- Priorizar zonas críticas.
- Generar explicaciones.
- Enriquecer contexto para análisis.
- Asistir en alertas y reportes.

Este enfoque permite mantener trazabilidad técnica en el procesamiento geoespacial y utilizar IA donde aporta mayor valor analítico.

---

## 📦 Módulos del Sistema

El sistema está organizado en módulos independientes pero encadenados:

| Módulo | Nombre | Responsabilidad |
|---|---|---|
| **M1** | Ingesta de Datos | Descarga y registro de datos satelitales, inicialmente productos SMAP desde NASA Earthdata. Diseño extensible para futuras fuentes como SAOCOM, NISAR, SMN e INDEC. |
| **M2** | ETL Geoespacial | Transformación de archivos HDF5 a GeoTIFF, validación, reproyección, clipping por región de interés y cálculo de estadísticas raster. |
| **M3** | Almacenamiento Geoespacial | Persistencia centralizada en PostgreSQL/PostGIS para capas procesadas, regiones, indicadores, riesgos, alertas, impactos económicos y auditoría. |
| **M4** | AI Core Ecosystem | Capa cognitiva basada en arquitectura hexagonal, con abstracción LLM, contexto, trazabilidad, herramientas y orquestación de agentes. |
| **M5** | Agentes Inteligentes | Agentes especializados para análisis hídrico-ambiental, riesgo, impacto económico-productivo y alertas tempranas. |
| **M6** | Conectores y Enriquecimiento | Integración de datos meteorológicos, indicadores socioeconómicos y contexto adicional para análisis asistido por IA. |

---

## 🔁 Flujo General

Satélites / APIs externas
        │
        ▼
M1: Ingesta de datos
        │
        ▼
M2: ETL geoespacial
        │
        ▼
M3: Almacenamiento PostGIS
        │
        ├── M6: Clima / Socioeconomía / Contexto
        │
        ▼
M4: AI Core Ecosystem
        │
        ▼
M5: Agentes inteligentes
        │
        ▼
Indicadores, riesgos, alertas y soporte a decisiones


---

## 🧱 Stack Técnico

| Capa                          | Tecnología                                 |
| ----------------------------- | ------------------------------------------ |
| **Lenguaje principal**        | Python 3.11+                               |
| **Ingesta**                   | earthaccess, h5py, requests                |
| **Procesamiento geoespacial** | rasterio, GDAL, shapely, rioxarray, numpy  |
| **Base de datos**             | PostgreSQL 15 + PostGIS                    |
| **IA / LLM**                  | LiteLLM, LangGraph, PydanticAI, jsonschema |
| **Observabilidad**            | OpenTelemetry, audit logs                  |
| **Infraestructura**           | Docker, Docker Compose                     |
| **Testing**                   | pytest, tests unitarios e integración      |

---

## 🚀 Primeros Pasos

### 1. Requisitos

* Python 3.11+
* Docker y Docker Compose
* Cuenta gratuita en NASA Earthdata Login

### 2. Clonar el repositorio

git clone https://github.com/Joassanchez/mse-space-platform.git
cd mse-space-platform


### 3. Configurar variables de entorno

cp .env.example .env

Completar en `.env` las credenciales necesarias:


EARTHDATA_USERNAME=
EARTHDATA_PASSWORD=
OPENWEATHER_API_KEY=


### 4. Levantar base de datos

docker compose up -d postgres

### 5. Ejecutar migraciones


for f in migrations/*.sql; do
  docker compose exec -T postgres psql -U mse_user -d mse_platform < "$f"
done

### 6. Ejecutar ingesta SMAP

docker compose run --rm ingestion


O directamente con Python:

pip install -r requirements.txt
python -m src.jobs.run_smap_ingestion

### 7. Ejecutar procesamiento geoespacial

docker compose run --rm geospatial


O vía CLI:

python -m src.geospatial.cli.process_smap


---

## 🧪 Tests

pytest tests/unit/
pytest tests/integration/ -m integration
pytest tests/ai/unit/
pytest tests/ai/integration/ -m integration


---

## 📁 Estructura del Proyecto

mse-space-platform/
├── src/
│   ├── config/              # Configuración YAML y validadores
│   ├── ingestion/           # M1: conectores de ingesta
│   ├── geospatial/          # M2: ETL geoespacial
│   ├── storage/             # M3: persistencia y metadatos
│   ├── ai/                  # M4: AI Core Ecosystem
│   ├── weather/             # M6: conectores meteorológicos
│   ├── jobs/                # Jobs batch
│   └── models/              # Modelos compartidos
│
├── migrations/              # Migraciones SQL
├── data/                    # Datos raw, processed y metadata
├── tests/                   # Tests unitarios e integración
├── scripts/                 # Scripts auxiliares
├── docs/                    # Documentación técnica y PRDs
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── pytest.ini

---

## 🏗️ Arquitectura por Módulo

### M1 — Ingesta de Datos

Módulo encargado de conectar con fuentes externas, autenticar, buscar, descargar, validar y registrar archivos crudos. Actualmente prioriza productos SMAP desde NASA Earthdata, con diseño extensible para nuevas fuentes satelitales, meteorológicas o estadísticas.

### M2 — ETL Geoespacial

Pipeline responsable de transformar datos crudos en capas geoespaciales procesadas. Incluye lectura de HDF5, validación, generación de GeoTIFF, cálculo de estadísticas, manejo de nodata, clipping opcional por región y trazabilidad del procesamiento.

### M3 — Almacenamiento Geoespacial

Capa central de persistencia basada en PostgreSQL/PostGIS. Permite almacenar regiones, geometrías, capas procesadas, indicadores, evaluaciones de riesgo, alertas, impactos económicos y eventos de auditoría.

### M4 — AI Core Ecosystem

Capa cognitiva del sistema. Integra abstracción de modelos LLM, motor de contexto, herramientas, trazabilidad, gestión de estado y orquestación de flujos de agentes. Opera sobre datos ya estructurados y procesados por las capas anteriores.

### M5 — Agentes Inteligentes

Conjunto de agentes especializados para tareas de análisis hídrico-ambiental, clasificación de riesgo, interpretación económica-productiva y generación de alertas tempranas. Su función es asistir el análisis, no reemplazar el procesamiento geoespacial determinístico.

### M6 — Conectores y Enriquecimiento

Módulo orientado a incorporar fuentes complementarias como datos meteorológicos, indicadores socioeconómicos y contexto territorial. Estos datos enriquecen los análisis y mejoran la calidad del contexto disponible para los agentes de IA.

---

## 🔐 Variables de Entorno

| Variable              | Requerida | Descripción                    |
| --------------------- | --------- | ------------------------------ |
| `EARTHDATA_USERNAME`  | Sí        | Usuario de NASA Earthdata      |
| `EARTHDATA_PASSWORD`  | Sí        | Contraseña de NASA Earthdata   |
| `MAX_DAYS_RANGE`      | No        | Máximo de días por consulta    |
| `OPENWEATHER_API_KEY` | No        | API key de OpenWeather para M6 |

---

## 📌 Estado del Proyecto

El proyecto se encuentra en desarrollo como MVP técnico para el hackatón. La prioridad actual es validar el flujo completo:

datos espaciales → procesamiento geoespacial → almacenamiento → indicadores → IA aplicada → alertas → visualización / soporte a decisiones

---

## 👥 Equipo

**MSE-Space**

Proyecto desarrollado para el desafío **“El poder de los datos desde el espacio”** del **Hackatón Argentina al Espacio**.
