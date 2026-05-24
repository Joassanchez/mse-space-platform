"""Script de exploración técnica del archivo SMAP HDF5 real.

Objetivos:
  - Inspeccionar grupos, datasets y atributos del HDF5.
  - Identificar variables de humedad del suelo disponibles.
  - Entender la metadata espacial (CRS, grilla, dimensiones).
  - Determinar la variable inicial a procesar en el Módulo 2.

Uso: python scripts/explore_hdf5.py
"""

import h5py
import numpy as np
from pathlib import Path

# Ruta al archivo real descargado por el Módulo 1
HDF5_PATH = Path("data/raw/smap/2023/12/SMAP_L4_SM_gph_20231231T223000_Vv8010_001.h5")


def inspect_group(name, obj, indent=0):
    """Recursively inspect HDF5 groups and datasets."""
    prefix = "  " * indent
    if isinstance(obj, h5py.Group):
        print(f"{prefix}[GROUP] {name}/")
        for attr_name in obj.attrs:
            attr_val = obj.attrs[attr_name]
            attr_repr = str(attr_val)
            if len(attr_repr) > 120:
                attr_repr = attr_repr[:120] + "..."
            print(f"{prefix}   attr: {attr_name} = {attr_repr}")
    elif isinstance(obj, h5py.Dataset):
        ds = obj
        print(f"{prefix}[DSET] {name}")
        print(f"{prefix}   shape: {ds.shape}")
        print(f"{prefix}   dtype: {ds.dtype}")
        print(f"{prefix}   chunks: {ds.chunks}")
        print(f"{prefix}   compression: {ds.compression}")
        print(f"{prefix}   fillvalue: {ds.fillvalue}")
        for attr_name in ds.attrs:
            attr_val = ds.attrs[attr_name]
            attr_repr = str(attr_val)
            if len(attr_repr) > 120:
                attr_repr = attr_repr[:120] + "..."
            print(f"{prefix}   attr: {attr_name} = {attr_repr}")
        # For 2D datasets, dump basic stats
        if ds.ndim == 2 and ds.size < 10_000_000:
            data = ds[()]
            valid = data[~np.isnan(data)] if np.issubdtype(ds.dtype, np.floating) else data
            print(f"{prefix}   dtype (native): {data.dtype}")
            if len(valid):
                print(f"{prefix}   min: {np.min(valid):>12.6f}")
                print(f"{prefix}   max: {np.max(valid):>12.6f}")
                print(f"{prefix}   mean:{np.mean(valid):>12.6f}")
            if np.issubdtype(ds.dtype, np.floating):
                print(f"{prefix}   nan count: {np.isnan(data).sum()}")

print(f"{'='*70}")
print(f"  SMAP HDF5 Exploration Report")
print(f"{'='*70}")
print(f"File: {HDF5_PATH}")
print(f"Size: {HDF5_PATH.stat().st_size / (1024*1024):.1f} MB")
print()

with h5py.File(str(HDF5_PATH), "r") as f:
    print(f"[ROOT] Attributes:")
    for attr_name in f.attrs:
        attr_val = f.attrs[attr_name]
        attr_repr = str(attr_val)
        if len(attr_repr) > 160:
            attr_repr = attr_repr[:160] + "..."
        print(f"     {attr_name} = {attr_repr}")
    print()

    # Full tree inspection
    print(f"{'='*70}")
    print(f"  FULL STRUCTURE")
    print(f"{'='*70}")
    f.visititems(lambda name, obj: inspect_group(name, obj))

    print()
    print(f"{'='*70}")
    print(f"  SUMMARY: KEY DATASETS IDENTIFIED")
    print(f"{'='*70}")

    # Common SMAP L4 variable locations to check
    potential_paths = [
        "/Geophysical_Data/sm_surface",
        "/Geophysical_Data/sm_rootzone",
        "/Geophysical_Data/sm_surface_wetness",
        "/Geophysical_Data/temp_soil",
        "/Geophysical_Data/sm_surface_analysis",
        "/Geophysical_Data/retrieval_quality_flag",
    ]

    for path in potential_paths:
        if path in f:
            ds = f[path]
            print(f"\n[FOUND] {path}")
            print(f"   shape:   {ds.shape}")
            print(f"   dtype:   {ds.dtype}")
            print(f"   chunks:  {ds.chunks}")
            print(f"   unit:    {ds.attrs.get('units', 'N/A')}")
            print(f"   long_name: {ds.attrs.get('long_name', 'N/A')}")
            # Load a sample (subset to avoid memory issues)
            data = ds[()] if ds.size < 500_000 else ds[::10, ::10]
            valid = data[~np.isnan(data)] if np.issubdtype(ds.dtype, np.floating) else data.flatten()
            if len(valid):
                print(f"   sample min:  {np.min(valid):.6f}")
                print(f"   sample max:  {np.max(valid):.6f}")
                print(f"   sample mean: {np.mean(valid):.6f}")
                print(f"   nan count:   {np.isnan(data).sum()}")
            if hasattr(ds, 'chunks') and ds.chunks:
                print(f"   chunk size:  {ds.chunks}")
        else:
            print(f"\n[NOT FOUND] {path}")
