````markdown
# PRD — Módulo 2: ETL Geoespacial SMAP

## 1. Descripción general

El Módulo 2 tiene como objetivo transformar los archivos crudos SMAP descargados en el Módulo 1 en capas geoespaciales procesadas, validadas y listas para análisis territorial.

El Módulo 1 resolvió la ingesta inicial de datos satelitales: autenticación con NASA Earthdata, búsqueda, descarga, particionado local, registro de metadata en PostgreSQL e idempotencia de archivos crudos. Sin embargo, esos archivos todavía se encuentran en formato HDF5 crudo y no pueden ser utilizados directamente por los módulos posteriores de indicadores, riesgo agroambiental, alertas o visualización.

Este módulo debe implementar un pipeline ETL geoespacial capaz de leer archivos SMAP L4 en formato HDF5, extraer variables relevantes de humedad del suelo, validar su estructura, convertir los datos a capas raster georreferenciadas y registrar la metadata del procesamiento.

El resultado esperado es una base geoespacial inicial confiable sobre la cual construir indicadores hídricos, análisis de sequía, mapas de riesgo y visualizaciones operativas.

---

## 2. Objetivo del módulo

Desarrollar un pipeline ETL geoespacial para procesar archivos SMAP L4 crudos, extraer información de humedad del suelo, generar capas raster georreferenciadas y registrar su trazabilidad en PostgreSQL.

En términos funcionales:

- Leer archivos HDF5 reales descargados desde NASA/NSIDC.
- Validar que los archivos contengan la estructura mínima esperada.
- Extraer variables relevantes de humedad del suelo.
- Convertir arrays científicos a capas raster geoespaciales.
- Generar archivos GeoTIFF procesados.
- Registrar metadata técnica y trazabilidad del procesamiento.
- Dejar los datos listos para módulos posteriores de indicadores, riesgo, alertas y dashboard.

---

## 3. Contexto del proyecto

El proyecto general busca construir una Plataforma Inteligente de Gestión Hídrica y Riesgo Agroambiental para Argentina, integrando datos satelitales, procesamiento geoespacial, análisis de riesgo, modelos de impacto económico, alertas tempranas e inteligencia artificial.

La arquitectura general acordada es híbrida:

- Los procesos determinísticos de ingesta, procesamiento geoespacial, almacenamiento y visualización se implementan mediante código, pipelines, servicios backend y librerías geoespaciales.
- La IA se reserva para análisis, interpretación, clasificación de riesgo, explicación, predicción inicial, alertas y soporte a decisiones.
- No habrá un orquestador general multiagente. El sistema se organizará mediante un pipeline modular y secuencial.

El Módulo 2 pertenece a la Capa ETL Geoespacial y es un componente base del MVP.

---

## 4. Relación con el Módulo 1

El Módulo 1 dejó implementado:

- Python 3.11.
- Ingesta mediante `earthaccess`.
- Producto SMAP L4 `SPL4SMGP.008`.
- Descarga de archivos HDF5 reales.
- Almacenamiento local en `data/raw/smap/YYYY/MM`.
- Registro de metadata en PostgreSQL.
- Idempotencia por `file_name`, `size_bytes` y SHA-256.
- Estados de ingesta: `pending`, `running`, `completed`, `completed_with_warnings`, `failed`.
- Arquitectura Clean/Hexagonal con conectores extensibles.
- Tests unitarios, tests de integración Earthdata y tests PostgreSQL.

El Módulo 2 debe consumir como entrada los archivos crudos y metadata generados por ese módulo.

---

## 5. Alcance funcional

El alcance funcional del Módulo 2 incluye:

### 5.1 Lectura de archivos HDF5 SMAP

El sistema debe poder abrir archivos SMAP L4 en formato HDF5 y explorar su estructura interna.

Debe permitir:

- Identificar grupos y datasets disponibles.
- Leer atributos técnicos relevantes.
- Obtener dimensiones de los arrays.
- Detectar unidades, valores nulos, fechas y metadata asociada.
- Extraer variables seleccionadas para procesamiento.

---

### 5.2 Validación de estructura

El sistema debe validar que cada archivo crudo sea apto para procesamiento.

Debe verificar:

- Que el archivo exista.
- Que sea legible como HDF5.
- Que contenga los grupos/datasets mínimos esperados.
- Que la variable seleccionada exista.
- Que la variable tenga dimensiones válidas.
- Que los valores se encuentren dentro de rangos razonables.
- Que se puedan identificar metadata temporal y espacial suficiente.
- Que los errores sean controlados y registrados.

---

### 5.3 Extracción de variables SMAP

El sistema debe extraer al menos una variable inicial de humedad del suelo.

Variable prioritaria sugerida:

- Humedad superficial del suelo.

Variables candidatas posteriores:

- Humedad de zona radicular.
- Temperatura del suelo.
- Flags o máscaras de calidad.
- Información temporal asociada al producto.

Para el MVP del Módulo 2, se recomienda procesar una variable principal y dejar la arquitectura preparada para agregar nuevas variables sin rediseñar el pipeline.

---

### 5.4 Conversión a raster geoespacial

El sistema debe convertir la variable extraída desde HDF5 a una capa raster geoespacial.

Debe generar archivos en formato:

- GeoTIFF como formato principal.

Cada GeoTIFF debe incluir, cuando sea técnicamente posible:

- CRS.
- Transform espacial.
- Resolución.
- Bounding box.
- Valor `nodata`.
- Tipo de dato.
- Metadata de variable.
- Fecha de adquisición.
- Fuente del dato.

---

### 5.5 Recorte por región de interés

El sistema debe permitir procesar los datos sobre una región de interés definida.

Para el MVP puede utilizarse:

- Argentina completa.
- Una provincia piloto.
- Una región agroproductiva específica.

El diseño debe permitir configurar la región de interés sin modificar la lógica central del pipeline.

---

### 5.6 Almacenamiento de outputs procesados

El sistema debe guardar los archivos procesados en una estructura ordenada.

Estructura sugerida:

```text
data/
  processed/
    smap/
      soil_moisture/
        YYYY/
          MM/
            smap_soil_moisture_YYYYMMDD.tif
````

El naming debe ser consistente, trazable y determinístico.

---

### 5.7 Persistencia de metadata en PostgreSQL

El sistema debe registrar en PostgreSQL la metadata de cada capa procesada.

La metadata debe vincular:

* Archivo crudo original.
* Job de procesamiento.
* Variable procesada.
* Ruta del archivo GeoTIFF.
* Fecha de adquisición.
* Estado del procesamiento.
* Estadísticas básicas.
* Errores o advertencias.

---

### 5.8 Idempotencia

El procesamiento debe ser idempotente.

Si un archivo crudo ya fue procesado para una variable determinada, el sistema no debe duplicar capas ni registros.

Debe poder:

* Detectar procesamiento previo.
* Reutilizar metadata existente cuando corresponda.
* Reprocesar únicamente si se indica explícitamente mediante una opción controlada.

---

### 5.9 Logging y trazabilidad

El sistema debe registrar logs claros durante todo el proceso.

Los logs deben permitir identificar:

* Archivo procesado.
* Variable seleccionada.
* Inicio y fin del procesamiento.
* Estado final.
* Ruta del output.
* Errores.
* Advertencias.
* Estadísticas básicas del raster.

---

## 6. Fuera de alcance

El Módulo 2 no debe incluir:

* Modelos de IA.
* Agentes inteligentes.
* Clasificación de riesgo.
* Alertas tempranas.
* Dashboard web.
* APIs públicas para usuarios finales.
* Predicción.
* Cálculo avanzado de sequía.
* Modelos de impacto económico.
* Integración con SAOCOM.
* Integración con NISAR.
* Integración con SMN.
* Integración con INDEC.
* Procesamiento multi-fuente.

Este módulo debe concentrarse en dejar una base geoespacial SMAP correcta, validada y trazable.

---

## 7. Usuarios objetivo del módulo

Este módulo no está orientado todavía a usuarios finales, sino a usuarios técnicos internos del sistema.

Usuarios principales:

1. Equipo de desarrollo.
2. Equipo de datos/geoespacial.
3. Módulos posteriores del sistema.
4. Pipeline analítico de indicadores y riesgo.
5. Futuro dashboard geoespacial.

---

## 8. Casos de uso

### CU-01 — Procesar archivo SMAP crudo

Como sistema, quiero tomar un archivo HDF5 descargado previamente para generar una capa raster procesada de humedad del suelo.

Criterio de aceptación:

* Dado un archivo HDF5 válido, el sistema genera un GeoTIFF y registra su metadata.

---

### CU-02 — Validar archivo antes de procesarlo

Como sistema, quiero validar la estructura del archivo antes de extraer datos para evitar fallos silenciosos o outputs incorrectos.

Criterio de aceptación:

* Si el archivo no contiene la variable requerida, el procesamiento falla de forma controlada y registra el error.

---

### CU-03 — Evitar reprocesamiento duplicado

Como sistema, quiero detectar si un archivo ya fue procesado para evitar duplicados.

Criterio de aceptación:

* Si el mismo archivo y variable ya fueron procesados, el sistema no crea una nueva capa salvo que se solicite reprocesamiento explícito.

---

### CU-04 — Registrar trazabilidad del procesamiento

Como equipo técnico, quiero saber de qué archivo crudo proviene cada capa procesada.

Criterio de aceptación:

* Cada capa procesada queda vinculada en PostgreSQL con el archivo raw original.

---

### CU-05 — Generar output usable por módulos posteriores

Como módulo de indicadores, quiero consumir capas GeoTIFF normalizadas para calcular métricas territoriales.

Criterio de aceptación:

* El GeoTIFF generado puede abrirse con Rasterio y contiene metadata espacial suficiente.

---

## 9. Requisitos funcionales

### RF-01 — Descubrimiento de archivos pendientes

El sistema debe poder identificar archivos SMAP crudos disponibles para procesamiento desde la metadata persistida por el Módulo 1.

---

### RF-02 — Lectura HDF5

El sistema debe implementar un componente capaz de abrir archivos HDF5 SMAP y acceder a sus grupos, datasets y atributos.

---

### RF-03 — Validación de estructura

El sistema debe validar la estructura mínima del archivo antes de iniciar la conversión geoespacial.

---

### RF-04 — Extracción de variable

El sistema debe extraer al menos una variable de humedad del suelo desde el archivo HDF5.

---

### RF-05 — Manejo de valores nulos

El sistema debe identificar y manejar correctamente valores nulos, inválidos o fuera de rango.

---

### RF-06 — Conversión a GeoTIFF

El sistema debe generar un archivo GeoTIFF georreferenciado a partir de la variable extraída.

---

### RF-07 — Metadata espacial

El sistema debe conservar o construir metadata espacial suficiente para que el output sea utilizable por herramientas GIS.

---

### RF-08 — Recorte por región de interés

El sistema debe permitir configurar una región de interés para limitar el área procesada.

---

### RF-09 — Estadísticas básicas

El sistema debe calcular estadísticas básicas del raster generado:

* Valor mínimo.
* Valor máximo.
* Valor medio.
* Cantidad de píxeles válidos.
* Cantidad de píxeles `nodata`.

---

### RF-10 — Persistencia de capa procesada

El sistema debe guardar en PostgreSQL un registro por cada capa procesada correctamente.

---

### RF-11 — Persistencia de job de procesamiento

El sistema debe registrar cada ejecución del pipeline como un job con estado, timestamps, errores y advertencias.

---

### RF-12 — Idempotencia

El sistema debe evitar duplicar registros y archivos procesados para la misma combinación de archivo crudo, variable y configuración de procesamiento.

---

### RF-13 — CLI de ejecución

El sistema debe exponer un comando CLI para ejecutar el procesamiento de archivos SMAP.

Ejemplos conceptuales:

```bash
python -m src.geospatial.cli.process_smap
python -m src.geospatial.cli.process_smap --raw-file-id <id>
python -m src.geospatial.cli.process_smap --limit 5
```

---

### RF-14 — Estados de procesamiento

El sistema debe manejar estados claros para los jobs geoespaciales:

* `pending`
* `running`
* `completed`
* `completed_with_warnings`
* `failed`
* `skipped`

---

### RF-15 — Errores controlados

El sistema debe capturar y registrar errores sin romper el procesamiento completo de múltiples archivos.

---

## 10. Requisitos no funcionales

### RNF-01 — Trazabilidad

Cada output debe ser rastreable hasta su archivo crudo original y su job de procesamiento.

---

### RNF-02 — Reproducibilidad

El mismo archivo, variable y configuración deben producir el mismo output lógico.

---

### RNF-03 — Extensibilidad

El diseño debe permitir agregar nuevas variables SMAP y futuras fuentes satelitales sin reescribir el pipeline completo.

---

### RNF-04 — Separación de responsabilidades

El módulo debe mantener separación entre:

* Lectura HDF5.
* Validación.
* Transformación geoespacial.
* Escritura raster.
* Persistencia.
* Orquestación.

---

### RNF-05 — Observabilidad técnica

El pipeline debe emitir logs suficientes para depuración y auditoría técnica.

---

### RNF-06 — Testeabilidad

Los componentes principales deben ser testeables de forma aislada.

---

### RNF-07 — Robustez

El sistema debe tolerar archivos inválidos, variables faltantes o errores de escritura sin corromper el estado general.

---

### RNF-08 — Performance razonable

El procesamiento debe ser eficiente para archivos SMAP individuales, evitando cargar datos innecesarios cuando sea posible.

---

### RNF-09 — Compatibilidad

El módulo debe integrarse con el stack existente del Módulo 1:

* Python 3.11.
* PostgreSQL.
* Docker/Docker Compose.
* Arquitectura Clean/Hexagonal.
* Pytest.
* Configuración por archivos/env vars.

---

## 11. Modelo de datos sugerido

### 11.1 Tabla `geospatial_processing_jobs`

Representa una ejecución del pipeline ETL geoespacial.

Campos sugeridos:

```text
id
raw_file_id
source_code
status
started_at
finished_at
error_message
warnings
output_layers_count
created_at
updated_at
```

Relación:

* `raw_file_id` referencia al archivo crudo registrado por el Módulo 1.

---

### 11.2 Tabla `processed_geospatial_layers`

Representa una capa raster generada.

Campos sugeridos:

```text
id
processing_job_id
raw_file_id
source_code
variable_name
display_name
file_path
file_format
crs
bbox
resolution_x
resolution_y
width
height
nodata_value
min_value
max_value
mean_value
valid_pixel_count
nodata_pixel_count
acquisition_date
processing_version
created_at
updated_at
```

Restricción sugerida:

```text
unique(raw_file_id, variable_name, processing_version)
```

Esta restricción ayuda a garantizar idempotencia.

---

## 12. Estructura técnica sugerida

La estructura debe respetar el enfoque Clean/Hexagonal ya utilizado en el Módulo 1.

Estructura conceptual:

```text
src/
  geospatial/
    domain/
      models.py
      errors.py
      ports.py

    application/
      smap_geospatial_service.py
      raster_processing_service.py
      geospatial_validation_service.py

    infrastructure/
      hdf5/
        smap_hdf5_reader.py

      raster/
        geotiff_writer.py
        raster_metadata_extractor.py

      persistence/
        geospatial_processing_repository.py
        processed_layer_repository.py

    cli/
      process_smap.py
```

---

## 13. Componentes principales

### 13.1 `SMAPHDF5Reader`

Responsable de abrir archivos SMAP HDF5 y extraer arrays, atributos y metadata.

No debe encargarse de escribir archivos ni persistir en base de datos.

---

### 13.2 `GeospatialValidationService`

Responsable de validar:

* Existencia del archivo.
* Estructura HDF5.
* Variable requerida.
* Dimensiones.
* Rangos.
* Metadata mínima.

---

### 13.3 `RasterProcessingService`

Responsable de preparar la matriz geoespacial para conversión raster.

Debe manejar:

* Valores nulos.
* Tipo de dato.
* Transform espacial.
* CRS.
* Recorte por región de interés.
* Estadísticas básicas.

---

### 13.4 `GeoTIFFWriter`

Responsable de escribir el archivo GeoTIFF en disco.

Debe garantizar que el archivo generado pueda abrirse con herramientas GIS estándar.

---

### 13.5 `ProcessedLayerRepository`

Responsable de guardar y consultar metadata de capas procesadas.

---

### 13.6 `SMAPGeospatialService`

Responsable de orquestar el flujo completo:

1. Buscar archivo crudo.
2. Validar idempotencia.
3. Crear job.
4. Leer HDF5.
5. Validar estructura.
6. Extraer variable.
7. Procesar raster.
8. Escribir GeoTIFF.
9. Registrar metadata.
10. Finalizar job.

---

## 14. Flujo funcional del módulo

```text
1. El sistema identifica archivos SMAP crudos con estado completed.
2. Verifica si ya fueron procesados.
3. Crea un job de procesamiento geoespacial.
4. Abre el archivo HDF5.
5. Valida estructura y variable requerida.
6. Extrae el array de humedad del suelo.
7. Aplica limpieza de valores inválidos/nodata.
8. Construye metadata espacial.
9. Opcionalmente recorta por región de interés.
10. Genera GeoTIFF.
11. Calcula estadísticas básicas.
12. Guarda metadata de la capa procesada.
13. Marca el job como completed o completed_with_warnings.
14. Si ocurre un error, marca el job como failed y registra el motivo.
```

---

## 15. Configuración

El módulo debe poder configurarse mediante archivo YAML o variables de entorno.

Configuración sugerida:

```yaml
geospatial:
  source: smap
  product: SPL4SMGP.008
  processing_version: v1

  variables:
    primary_soil_moisture:
      enabled: true
      output_name: soil_moisture
      nodata_value: -9999

  output:
    base_dir: data/processed/smap
    format: geotiff

  region_of_interest:
    enabled: true
    name: argentina
    vector_path: data/reference/argentina_boundary.geojson

  validation:
    fail_on_missing_variable: true
    fail_on_invalid_dimensions: true
```

---

## 16. Testing requerido

### 16.1 Tests unitarios

Deben cubrir:

* Reader HDF5.
* Validador de estructura.
* Normalización de valores nulos.
* Generación de rutas de output.
* Cálculo de estadísticas.
* Reglas de idempotencia.
* Manejo de errores.

---

### 16.2 Tests de integración

Deben cubrir:

* Procesamiento de un archivo HDF5 real descargado en el Módulo 1.
* Generación de GeoTIFF.
* Apertura del GeoTIFF con Rasterio.
* Persistencia de metadata en PostgreSQL.
* No duplicación ante reprocesamiento.

---

### 16.3 Validaciones mínimas esperadas

El módulo debe pasar:

```bash
pytest
```

Y, si existen scripts específicos:

```bash
pytest tests/geospatial/
pytest tests/integration/
```

---

## 17. Criterios de aceptación

El Módulo 2 se considera terminado cuando:

* El sistema puede tomar al menos un archivo SMAP HDF5 real descargado en el Módulo 1.
* El sistema puede abrir y validar correctamente ese archivo.
* El sistema puede extraer al menos una variable relevante de humedad del suelo.
* El sistema puede generar un GeoTIFF válido.
* El GeoTIFF puede abrirse con Rasterio.
* El output contiene metadata espacial suficiente.
* El output se guarda en una estructura clara bajo `data/processed`.
* La metadata del procesamiento queda registrada en PostgreSQL.
* Cada capa procesada queda vinculada al archivo crudo original.
* El procesamiento es idempotente.
* Los errores se registran de forma controlada.
* Existen tests unitarios e integración.
* La documentación del módulo explica cómo ejecutar el procesamiento.
* El estado SDD/OpenSpec del módulo queda verificado y archivado.

---

## 18. Riesgos técnicos

### R-01 — Georreferenciación incorrecta

El principal riesgo técnico es interpretar incorrectamente la grilla espacial del producto SMAP. No debe asumirse que todo array HDF5 puede convertirse directamente a GeoTIFF sin analizar su metadata espacial.

Mitigación:

* Realizar primero una exploración técnica del HDF5 real.
* Documentar variables, dimensiones, atributos y proyección.
* Validar el GeoTIFF resultante con Rasterio y, si es posible, con QGIS.

---

### R-02 — Selección prematura de demasiadas variables

Procesar muchas variables desde el inicio puede aumentar complejidad y riesgo.

Mitigación:

* Procesar primero una variable principal.
* Diseñar el módulo para agregar más variables después.

---

### R-03 — Falta de metadata espacial suficiente

Puede ocurrir que la metadata necesaria no esté disponible de forma directa o requiera interpretación específica del producto.

Mitigación:

* Analizar documentación del producto SMAP.
* Encapsular la lógica espacial en un componente especializado.
* Registrar advertencias cuando la metadata sea parcial.

---

### R-04 — Archivos grandes o procesamiento pesado

Los archivos HDF5 pueden ser grandes y requerir uso cuidadoso de memoria.

Mitigación:

* Evitar cargar datos innecesarios.
* Procesar solo variables seleccionadas.
* Mantener el procesamiento por archivo.
* Medir tiempos básicos durante integración.

---

### R-05 — Duplicación de outputs

Sin idempotencia, el sistema podría generar múltiples capas para el mismo archivo y variable.

Mitigación:

* Agregar restricción única por `raw_file_id`, `variable_name` y `processing_version`.
* Validar existencia antes de procesar.
* Registrar jobs `skipped` cuando corresponda.

---

## 19. Plan de implementación sugerido

### Slice 1 — Exploración técnica del HDF5 real

Objetivo:

Entender la estructura real del archivo SMAP descargado.

Tareas:

* Inspeccionar grupos y datasets.
* Identificar variables disponibles.
* Revisar atributos, unidades y dimensiones.
* Determinar variable inicial a procesar.
* Documentar estrategia de conversión.

Resultado esperado:

* Reporte técnico breve de estructura HDF5.
* Variable inicial seleccionada.
* Decisión sobre georreferenciación y salida raster.

---

### Slice 2 — Reader y validator SMAP

Objetivo:

Implementar lectura y validación controlada del archivo HDF5.

Tareas:

* Crear `SMAPHDF5Reader`.
* Crear modelos internos de metadata.
* Crear `GeospatialValidationService`.
* Manejar errores específicos.
* Agregar tests unitarios.

Resultado esperado:

* El sistema puede abrir el archivo, leer metadata y validar la variable seleccionada.

---

### Slice 3 — Conversión a GeoTIFF

Objetivo:

Generar el primer raster geoespacial procesado.

Tareas:

* Implementar procesamiento de array.
* Manejar nodata.
* Construir transform espacial y CRS.
* Crear `GeoTIFFWriter`.
* Validar apertura con Rasterio.
* Guardar output en `data/processed`.

Resultado esperado:

* GeoTIFF válido generado desde un HDF5 real.

---

### Slice 4 — Persistencia e idempotencia

Objetivo:

Registrar metadata del procesamiento y evitar duplicados.

Tareas:

* Crear migraciones/tables de jobs y capas procesadas.
* Implementar repositorios.
* Vincular capa procesada con raw file.
* Implementar regla de idempotencia.
* Agregar tests de integración con PostgreSQL.

Resultado esperado:

* Cada output queda registrado y trazado en base de datos.

---

### Slice 5 — CLI, integración y verificación

Objetivo:

Cerrar el módulo con ejecución completa y verificable.

Tareas:

* Crear comando CLI.
* Procesar archivo real de punta a punta.
* Agregar logs claros.
* Agregar documentación de ejecución.
* Ejecutar tests.
* Actualizar estado SDD/OpenSpec.
* Crear verify-report.
* Archivar módulo.

Resultado esperado:

* Módulo 2 terminado, testeado, documentado y listo para habilitar el Módulo 3.

---

## 20. Resultado esperado final

Al finalizar el Módulo 2, el sistema deberá poder demostrar el siguiente flujo:

```text
Archivo SMAP HDF5 crudo
        ↓
Lectura y validación
        ↓
Extracción de humedad del suelo
        ↓
Conversión geoespacial
        ↓
GeoTIFF procesado
        ↓
Metadata persistida en PostgreSQL
        ↓
Datos listos para indicadores, riesgo y visualización
```

Resultado funcional esperado: A partir de un archivo satelital SMAP real descargado automáticamente, el sistema puede extraer humedad del suelo, convertirla en una capa geoespacial estándar, registrar su trazabilidad y dejarla lista para análisis territorial.

---

## 21. Decisiones técnicas iniciales

* El formato de salida principal será GeoTIFF.
* SMAP será la primera fuente procesada.
* Se procesará inicialmente una variable principal de humedad del suelo.
* PostgreSQL seguirá siendo la base de metadata.
* El almacenamiento de archivos seguirá siendo local dentro de `data/`.
* La arquitectura seguirá el enfoque Clean/Hexagonal usado en el Módulo 1.
* El módulo no incorporará IA.
* El módulo no calculará todavía riesgo ni alertas.
* El procesamiento deberá ser idempotente.
* El pipeline deberá quedar preparado para futuras fuentes como SAOCOM, NISAR, SMN e INDEC.

---

## 22. Próximo módulo habilitado

Una vez completado el Módulo 2, el proyecto queda preparado para avanzar al Módulo 3.

Módulo 3 sugerido:

# Indicadores Hídrico-Ambientales Iniciales

Objetivo del Módulo 3:

* Calcular indicadores derivados de las capas SMAP procesadas.
* Generar métricas territoriales simples.
* Comparar valores por región.
* Detectar umbrales iniciales de humedad baja, normal o alta.
* Preparar la base para riesgo agroambiental y alertas.

```
```
