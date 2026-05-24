 # Delta for geotiff-writing

 ## ADDED Requirements

 ### Requirement: Generic GeoTIFF Writer

 The system MUST provide a generic `GeoTIFFWriter` component that accepts standard raster arrays and spatial metadata, remaining completely agnostic to the original raw data source.

 #### Scenario: Write data from multiple sources

 - GIVEN generic processed raster arrays from different sources
 - WHEN the `GeoTIFFWriter` is invoked
 - THEN it MUST write valid GeoTIFFs for all sources using the provided metadata

 ### Requirement: Safe Writing Strategy

 The writer MUST avoid leaving partial or corrupt files on disk. It MUST write to a temporary file first and move it to the final destination only after a successful write and validation.

 #### Scenario: Safe writing process

 - GIVEN a processed array ready to be written
 - WHEN the writing process executes
 - THEN it MUST write to a temporary path
 - AND only move the file to the final path once writing completes successfully

 ### Requirement: Deterministic Output Paths

 The system MUST derive the output path deterministically from the source, variable, acquisition date, and processing_version.

 #### Scenario: Generate deterministic path

 - GIVEN a processing job
 - WHEN the output file path is calculated
 - THEN it MUST be uniquely and predictably based on the source metadata and processing version
 - AND output must be traceable to the original raw file

 ## MODIFIED Requirements

 ### Requirement: Spatial Metadata Inclusion (RF-07)

 The system MUST ensure the generated GeoTIFF includes sufficient spatial metadata (CRS, transform, bounding box, nodata value, resolution) to be usable by standard GIS tools. The CRS MUST be validated or derived for the product, avoiding hardcoded assumptions like EPSG:6933.

 #### Scenario: Verify spatial metadata in output

 - GIVEN a successful GeoTIFF write operation
 - WHEN the file is inspected using GIS tools or libraries like Rasterio
 - THEN it MUST properly report its validated/derived CRS and spatial transform
 - AND NOT rely on hardcoded CRS values

 #### Scenario: Writing fails due to disk issues

 - GIVEN a processed array ready to be written
 - WHEN the disk is full or permissions are denied
 - THEN it MUST throw a controlled error and ensure no corrupted partial file is left
