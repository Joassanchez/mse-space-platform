# hdf5-reading Specification

## Purpose
Lectura y parsing de archivos SMAP HDF5 (grupos, datasets, atributos, variables).

## Requirements

### Requirement: Open and Read HDF5 File (RF-02)
The system MUST implement a component capable of opening SMAP HDF5 files and accessing their internal structure without loading unnecessary datasets into memory.

#### Scenario: Successfully open a valid SMAP HDF5 file
- GIVEN a valid SMAP HDF5 file path
- WHEN the system attempts to open it
- THEN it MUST successfully read the root group and available datasets
- AND make technical attributes accessible

#### Scenario: Attempt to open an invalid file
- GIVEN a corrupted or non-HDF5 file
- WHEN the system attempts to open it
- THEN it MUST throw a controlled error indicating the read failure

### Requirement: Extract Soil Moisture Variable (RF-04)
The system MUST extract the configured soil moisture variable (e.g., `Geophysical_Data/sm_surface`) as a scientific array.

#### Scenario: Extract existing variable
- GIVEN a valid HDF5 file containing `Geophysical_Data/sm_surface`
- WHEN the system requests the extraction of this variable
- THEN it MUST return the full 2D array and its associated attributes

#### Scenario: Variable missing
- GIVEN an HDF5 file that does not contain the requested variable
- WHEN the system requests its extraction
- THEN it MUST raise a controlled error to prevent silent failures
