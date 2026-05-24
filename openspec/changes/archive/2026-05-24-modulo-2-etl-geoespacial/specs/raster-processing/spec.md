 # Delta for raster-processing

 ## ADDED Requirements

 ### Requirement: Generic Raster Processing

 The system MUST use a generic `RasterProcessingService` that works with standard arrays and metadata, decoupled from any specific source format (like HDF5 or SMAP).

 #### Scenario: Process generic raster data

 - GIVEN an array and its spatial metadata from any source
 - WHEN the generic raster processor is invoked
 - THEN it MUST process it successfully without relying on source-specific attributes

 ## MODIFIED Requirements

 ### Requirement: Region of Interest (ROI) Clipping (RF-08)

 The system MUST allow configuring an ROI to limit the processed area. If ROI is enabled, the geometry MUST be reprojected to the raster's CRS before clipping. If ROI is disabled, the pipeline MUST be able to generate the full raster without clipping.

 #### Scenario: Clip processing by configured ROI

 - GIVEN a configured ROI vector and a prepared global raster array
 - WHEN the processing step applies the ROI
 - THEN it MUST reproject the ROI to the raster's CRS and output only the spatial subset intersecting it

 #### Scenario: Process without ROI clipping

 - GIVEN a pipeline configuration with ROI disabled
 - WHEN the processing step executes
 - THEN it MUST process and output the entire raster without spatial clipping
