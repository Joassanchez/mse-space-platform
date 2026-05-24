# PRD - Módulo 1: Ingesta de Datos SMAP

## 1. Descripción general

El Módulo 1 tiene como objetivo implementar una capa de ingesta automatizada para obtener datos de humedad del suelo provenientes de SMAP, a través de NASA Earthdata / NSIDC. Este módulo será responsable de buscar, descargar, validar, almacenar y registrar metadatos de los archivos crudos necesarios para alimentar el pipeline geoespacial posterior.

Aunque la primera fuente implementada será SMAP, el módulo deberá diseñarse de forma extensible para permitir la incorporación futura de otras fuentes satelitales, meteorológicas, estadísticas o económicas, como SAOCOM, NISAR, SMN o INDEC.

## 2. Objetivo del módulo

Construir una capa inicial de ingesta de datos que permita consumir automáticamente productos SMAP relacionados con humedad del suelo, guardarlos de forma trazable y dejarlos disponibles para el Módulo 2 de procesamiento ETL geoespacial.

El módulo no debe calcular indicadores, clasificar riesgos, generar alertas ni ejecutar análisis con IA. Su responsabilidad termina cuando los datos crudos quedan descargados, validados, registrados y marcados como listos para procesamiento.

## 3. Fuente inicial: SMAP

La fuente inicial será SMAP, específicamente productos de humedad del suelo distribuidos por NASA Earthdata / NSIDC.

Producto recomendado para el MVP:

- Fuente: SMAP / NASA / NSIDC.
- Producto: SPL4SMGP.
- Versión: 008.
- Tipo de dato: humedad del suelo superficial y humedad de zona radicular.
- Formato esperado: HDF5.
- Acceso: NASA Earthdata Login.
- Consumo programático: Python + earthaccess.
- Uso dentro del sistema: alimentar indicadores de humedad, sequía y riesgo hídrico en módulos posteriores.

## 4. Alcance funcional

El módulo deberá permitir:

- Configurar una región piloto mediante bounding box.
- Configurar un rango temporal de consulta.
- Autenticarse contra NASA Earthdata.
- Buscar productos SMAP disponibles.
- Descargar archivos crudos en formato HDF5.
- Guardar los archivos en una estructura ordenada.
- Calcular checksum de cada archivo.
- Registrar metadatos básicos.
- Registrar el estado del proceso de ingesta.
- Marcar los archivos como `ready_for_etl`.
- Manejar errores de autenticación, búsqueda, descarga o validación.

## 5. Fuera de alcance

Este módulo no incluirá:

- Cálculo de humedad promedio.
- Recorte geoespacial avanzado.
- Reproyección de raster.
- Conversión final a GeoTIFF.
- Clasificación de sequía.
- Clasificación de riesgo.
- Generación de alertas.
- Visualización en dashboard.
- Análisis con IA.
- Automatización de otras fuentes distintas a SMAP en la primera versión.

Estas responsabilidades pertenecen a módulos posteriores.

## 6. Requisitos funcionales

### RF-01. Configuración de fuente

El sistema deberá contar con una configuración declarativa para SMAP, incluyendo código de producto, versión, proveedor, formato, variables esperadas y método de acceso.

Ejemplo:

```yaml
sources:
  smap:
    provider: NASA_NSIDC
    short_name: SPL4SMGP
    version: "008"
    format: HDF5
    access_method: earthaccess
    requires_auth: true
    variables:
      - sm_surface
      - sm_rootzone
````

### RF-02. Autenticación

El sistema deberá autenticarse contra NASA Earthdata utilizando credenciales configuradas por variables de entorno o archivo `.netrc`.

Variables sugeridas:

```env
EARTHDATA_USERNAME=
EARTHDATA_PASSWORD=
```

### RF-03. Búsqueda de datos

El sistema deberá buscar productos SMAP usando:

* `short_name`
* `version`
* `date_from`
* `date_to`
* `bounding_box`

Ejemplo de entrada:

```json
{
  "source": "SMAP",
  "regionId": "cordoba_pilot",
  "bbox": [-65.5, -34.8, -62.0, -30.0],
  "dateFrom": "2024-01-01",
  "dateTo": "2024-01-31"
}
```

### RF-04. Descarga de datos

El sistema deberá descargar los archivos encontrados y almacenarlos en:

```text
data/raw/smap/SPL4SMGP/YYYY/MM/
```

Los datos descargados no deberán modificarse. Toda transformación posterior deberá generar nuevos archivos en `data/processed`.

### RF-05. Registro de metadatos

Por cada archivo descargado, el sistema deberá registrar:

* Fuente.
* Producto.
* Versión.
* Fecha de consulta.
* Región.
* Bounding box.
* Ruta local.
* Nombre del archivo.
* Tamaño en bytes.
* Checksum SHA-256.
* Formato.
* Estado.
* Fecha de descarga.

### RF-06. Validación mínima

El sistema deberá validar:

* Que el archivo exista.
* Que el archivo no esté vacío.
* Que tenga extensión esperada.
* Que se pueda calcular checksum.
* Que el proceso tenga metadatos mínimos completos.

### RF-07. Estado de ingesta

Cada ejecución deberá generar un `ingestion_job` con uno de los siguientes estados:

```text
pending
running
completed
completed_with_warnings
failed
```

### RF-08. Salida del módulo

La salida del módulo deberá indicar si los archivos quedaron listos para ETL.

Ejemplo:

```json
{
  "jobId": "ing_001",
  "source": "SMAP",
  "dataset": "SPL4SMGP",
  "status": "completed",
  "filesCount": 12,
  "readyForETL": true
}
```

## 7. Requisitos no funcionales

* El módulo debe ser reproducible.
* El módulo debe ser extensible para futuras fuentes.
* Los datos crudos no deben ser sobrescritos sin control.
* Las credenciales no deben guardarse en código.
* Cada descarga debe quedar trazada.
* Los errores deben registrarse de forma clara.
* La estructura debe permitir ejecución manual y futura automatización programada.
* El diseño debe permitir agregar nuevos conectores sin modificar la lógica central.

## 8. Arquitectura interna sugerida

```text
geospatial-pipeline/
└── src/
    ├── config/
    │   └── sources.yaml
    │
    ├── ingestion/
    │   ├── base_connector.py
    │   └── smap/
    │       ├── smap_connector.py
    │       ├── smap_downloader.py
    │       ├── smap_metadata.py
    │       └── smap_job.py
    │
    ├── storage/
    │   ├── raw_storage.py
    │   └── metadata_repository.py
    │
    └── jobs/
        └── run_smap_ingestion.py
```

## 9. Diseño flexible para futuras fuentes

Aunque la primera fuente sea SMAP, el módulo deberá usar una interfaz común de conector.

Cada fuente futura deberá implementar:

```text
search()
download()
validate()
extract_metadata()
register()
```

Ejemplo conceptual:

```text
BaseIngestionConnector
  ├── SmapConnector
  ├── SaocomConnector
  ├── NisarConnector
  ├── SmnConnector
  └── IndecConnector
```

Esto permitirá agregar nuevas fuentes sin cambiar el flujo general del módulo.

## 10. Flujo operativo

```text
1. Recibir región piloto y rango temporal.
2. Leer configuración de SMAP.
3. Autenticarse contra NASA Earthdata.
4. Buscar productos SPL4SMGP disponibles.
5. Descargar archivos HDF5.
6. Guardar archivos en data/raw.
7. Calcular checksum.
8. Registrar metadatos.
9. Validar archivos.
10. Crear o actualizar ingestion_job.
11. Marcar archivos como ready_for_etl.
```

## 11. Modelo de datos mínimo

### data_sources

```text
id
code
name
provider
type
access_method
requires_auth
is_active
created_at
updated_at
```

### datasets

```text
id
source_id
short_name
version
format
variables
spatial_resolution
temporal_resolution
created_at
updated_at
```

### ingestion_jobs

```text
id
source_id
dataset_id
region_id
date_from
date_to
bbox
status
started_at
finished_at
error_message
created_at
```

### raw_files

```text
id
ingestion_job_id
source_id
dataset_id
file_path
file_name
file_format
checksum_sha256
size_bytes
metadata_json
ready_for_etl
created_at
```

## 12. Stack técnico recomendado

* Python.
* earthaccess.
* requests.
* h5py.
* xarray.
* pandas.
* numpy.
* PostgreSQL.
* PostGIS.
* Docker Compose.

En este módulo, `h5py`, `xarray`, `rasterio` o `rioxarray` podrán instalarse desde el inicio, pero el procesamiento avanzado de los HDF5 corresponderá al Módulo 2.

## 13. Criterios de aceptación

El módulo se considera completado para el MVP si:

* Existe una configuración declarativa de SMAP.
* El sistema puede autenticarse contra NASA Earthdata.
* El sistema puede buscar productos `SPL4SMGP.008` por fecha y bounding box.
* El sistema puede descargar archivos HDF5.
* Los archivos quedan guardados en `data/raw/smap`.
* Cada archivo tiene metadatos registrados.
* Cada archivo tiene checksum.
* Cada ejecución genera un `ingestion_job`.
* Los errores se registran correctamente.
* La salida indica `ready_for_etl = true`.
* La estructura permite agregar futuras fuentes mediante nuevos conectores.

## 14. Criterio mínimo demostrable

Dada una región piloto y un rango temporal, el sistema debe poder buscar y descargar datos SMAP de humedad del suelo, guardar los archivos crudos, registrar sus metadatos y dejarlos disponibles para el siguiente módulo de ETL geoespacial.

## 15. Decisión técnica final

Para el MVP, el Módulo 1 se implementará primero con SMAP porque permite automatización real mediante NASA Earthdata y `earthaccess`. El diseño, sin embargo, deberá mantenerse desacoplado y extensible para que fuentes futuras como SAOCOM, NISAR, SMN o INDEC puedan incorporarse sin rediseñar la arquitectura de ingesta.
