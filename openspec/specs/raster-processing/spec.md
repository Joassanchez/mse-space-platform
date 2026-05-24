# raster-processing Specification

## Purpose
Conversión de arrays científicos a raster geoespacial (CRS, transform, nodata, ROI).

## Requirements

### Requirement: Nodata and Invalid Value Handling (RF-05)
The system MUST properly identify and handle invalid or null values (e.g., `-9999.0`) to ensure they are interpreted as `nodata` in the output raster.

#### Scenario: Processing an array with nodata values
- GIVEN an extracted array containing `-9999.0` values
- WHEN the raster processing service prepares it
- THEN it MUST flag these pixels as `nodata` for the raster conversion

### Requirement: Region of Interest (ROI) Clipping (RF-08)
The system MUST allow configuring an ROI (e.g., Argentina) to limit the processed area, projecting the ROI (EPSG:4326) to the raster's CRS (EPSG:6933) before clipping.

#### Scenario: Clip processing by configured ROI
- GIVEN a configured ROI vector and a prepared global raster array
- WHEN the processing step applies the ROI
- THEN it MUST output only the spatial subset intersecting the ROI

### Requirement: Basic Statistics Calculation (RF-09)
The system MUST calculate basic statistics for the generated raster (min, max, mean, valid pixels, nodata pixels).

#### Scenario: Calculate stats for a processed raster
- GIVEN a processed raster array ready for output
- WHEN the statistics are computed
- THEN it MUST accurately report min, max, mean, and pixel counts, ignoring `nodata` values
