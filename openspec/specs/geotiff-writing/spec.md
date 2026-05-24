# geotiff-writing Specification

## Purpose
Escritura de archivos GeoTIFF con metadata espacial completa.

## Requirements

### Requirement: Conversion to GeoTIFF (RF-06)
The system MUST generate a georeferenced GeoTIFF file from the processed array.

#### Scenario: Write a standard GeoTIFF
- GIVEN a processed geospatial array and its destination path
- WHEN the writer component executes
- THEN it MUST create a valid GeoTIFF file on disk

### Requirement: Spatial Metadata Inclusion (RF-07)
The system MUST ensure the generated GeoTIFF includes sufficient spatial metadata (CRS, transform, bounding box, nodata value, resolution) to be usable by standard GIS tools.

#### Scenario: Verify spatial metadata in output
- GIVEN a successful GeoTIFF write operation
- WHEN the file is inspected using GIS tools or libraries like Rasterio
- THEN it MUST properly report its CRS (e.g., EPSG:6933) and spatial transform

#### Scenario: Writing fails due to disk issues
- GIVEN a processed array ready to be written
- WHEN the disk is full or permissions are denied
- THEN it MUST throw a controlled error and ensure no corrupted partial file is left
