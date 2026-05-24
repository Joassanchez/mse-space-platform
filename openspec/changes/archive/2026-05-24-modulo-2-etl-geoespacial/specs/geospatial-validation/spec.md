 # Delta for geospatial-validation

 ## ADDED Requirements

 ### Requirement: Generic Geospatial Validator Interface

 The system MUST define a generic `GeospatialValidator` interface that abstracts source-specific validation rules, with `SMAPValidationService` as its first concrete implementation.

 #### Scenario: Validate via generic interface

 - GIVEN a pipeline processing a geospatial file
 - WHEN validation is required
 - THEN it MUST invoke the generic `GeospatialValidator` interface

 ## MODIFIED Requirements

 ### Requirement: Structural Validation (RF-03)

 The system MUST validate that the file meets the minimum expected structure, deriving expected dimensions (e.g., the 1624x3856 grid for SMAP) from configuration, metadata, or validated product assumptions before any geospatial conversion starts.

 #### Scenario: File meets all structural requirements

 - GIVEN an HDF5 file with valid groups, dimensions, and variables matching its source configuration
 - WHEN the validation service inspects it
 - THEN it MUST pass the validation step

 #### Scenario: Invalid dimensions detected

 - GIVEN an HDF5 file where the array does not match the expected dimensions derived from its configuration
 - WHEN the validation service inspects it
 - THEN it MUST fail validation and log the unexpected dimensions

 ### Requirement: Range and Metadata Validation

 The system MUST validate that the extracted variable contains values within expected scientific ranges and has necessary spatial metadata attributes.

 #### Scenario: Values within expected ranges

 - GIVEN an extracted variable array
 - WHEN the validation service checks its data range
 - THEN it MUST confirm values are within physically possible soil moisture bounds (excluding nodata)

 #### Scenario: Missing essential metadata

 - GIVEN an HDF5 file missing critical attributes required for georeferencing
 - WHEN the validation service inspects it
 - THEN it MUST fail validation and report the missing metadata
