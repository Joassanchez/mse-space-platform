# geospatial-validation Specification

## Purpose
Validación de estructura HDF5, dimensiones, rangos y metadata mínima.

## Requirements

### Requirement: Structural Validation (RF-03)
The system MUST validate that the file meets the minimum expected structure before any geospatial conversion starts.

#### Scenario: File meets all structural requirements
- GIVEN an HDF5 file with valid groups, dimensions, and variables
- WHEN the validation service inspects it
- THEN it MUST pass the validation step

#### Scenario: Invalid dimensions detected
- GIVEN an HDF5 file where the soil moisture array does not match the expected 1624x3856 grid
- WHEN the validation service inspects it
- THEN it MUST fail validation and log the unexpected dimensions

### Requirement: Range and Metadata Validation
The system SHOULD validate that the extracted variable contains values within expected scientific ranges and has necessary spatial metadata attributes.

#### Scenario: Values within expected ranges
- GIVEN an extracted variable array
- WHEN the validation service checks its data range
- THEN it MUST confirm values are within physically possible soil moisture bounds (excluding nodata)

#### Scenario: Missing essential metadata
- GIVEN an HDF5 file missing critical attributes required for georeferencing
- WHEN the validation service inspects it
- THEN it MUST fail validation and report the missing metadata
