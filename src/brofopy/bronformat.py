"""BronFormat data structure module.

Provides a hierarchical structure for Bronformat data that mirrors the HDF5 file structure:
- BronFormat is the root container with entity types as attributes
- Each entity is a dict of entries (keyed by BROID/ID)
- Each entry contains groups (sub-entities like Adm, Dossier, Source, etc.)
- Time series data is stored as list of dicts under "Measurements" key

DataFrames and ObsCollections are created via conversion methods that delegate
to ext/pd.py and ext/hpd.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Self

import pandas as pd
from hydropandas import ObsCollection


@dataclass
class BronFormat:
    """Root container for Bronformat data with entity types as attributes.

    Mirrors the HDF5 file structure, with entities as attributes.
    Each entity contains a dictionary of entries (keyed by BROID/ID).
    Each entry contains sub-entities (groups) with their data.

    Attributes
    ----------
    GMN : dict | None
        Groundwater Monitoring Network.
    GMW : dict | None
        Groundwater Monitoring Well.
    GLD : dict | None
        Groundwater Level Data.
    GAR : dict | None
        Groundwater Analysis Results.
    BHR : dict | None
        Borehole.
    GUF : dict | None
        Groundwater Extraction Facilities.
    GPD : dict | None
        Groundwater Permission Documents.
    Proces : dict | None
        Process.
    IN : dict | None
        Instrument.
    QC : dict | None
        Quality Control.
    File : dict | None
        File.
    GIS : dict | None
        Geographic Information System.
    Cache : dict | None
        Cache.
    SAD : dict | None
        Soil Analysis Data.
    """

    GMN: dict[str, Any] | None = None
    GMW: dict[str, Any] | None = None
    GLD: dict[str, Any] | None = None
    GAR: dict[str, Any] | None = None
    BHR: dict[str, Any] | None = None
    GUF: dict[str, Any] | None = None
    GPD: dict[str, Any] | None = None
    Proces: dict[str, Any] | None = None
    IN: dict[str, Any] | None = None
    QC: dict[str, Any] | None = None
    File: dict[str, Any] | None = None
    GIS: dict[str, Any] | None = None
    Cache: dict[str, Any] | None = None
    SAD: dict[str, Any] | None = None

    def __repr__(self) -> str:
        """Representation of the BronFormat object."""
        entities = [name for name, val in self.__dict__.items() if val is not None]
        return f"BronFormat({', '.join(sorted(entities))})"

    def to_dict(self) -> dict[str, Any]:
        """Convert entire structure to nested dictionary."""
        return {name: val for name, val in self.__dict__.items() if val is not None}

    def print(self, indent: int = 0) -> None:
        """Pretty print the structure."""

        def _print_dict(d: dict, indent: int) -> None:
            """Pretty print a dictionary."""
            prefix = "  " * indent
            for key, val in d.items():
                if isinstance(val, dict):
                    print(f"{prefix}{key}/ (group)")
                    _print_dict(val, indent + 1)
                else:
                    val_type = type(val).__name__
                    if hasattr(val, "__len__") and not isinstance(val, str):
                        print(f"{prefix}{key}: {val_type} with {len(val)} items")
                    else:
                        print(f"{prefix}{key}: {val_type} = {val}")

        prefix = "  " * indent
        for name, val in self.__dict__.items():
            if val is None:
                continue
            print(f"{prefix}{name}/ (group)")
            _print_dict(val, indent + 1)

    @classmethod
    def from_file(cls, filepath: str | Path, backend: str = "auto") -> Self:
        """Create BronFormat object from a file.

        Parameters
        ----------
        filepath : str or Path
            Path to .bron2, .bronx, or .hdf5 file.
        backend : str, optional
            Backend to use: "auto", "scipy", or "h5py".
            - "auto": Automatically select backend based on file extension
            - "scipy": Use scipy backend (for .bron2 files)
            - "h5py": Use h5py backend (for .hdf5, .bronx files)
            By default "auto".

        Returns
        -------
        BronFormat
            BronFormat object with entity types as attributes.
            Each entity contains nested dictionaries mirroring the HDF5 structure.

        """
        from brofopy.reader import read_bronformat as _read_bronformat

        return _read_bronformat(filepath=filepath, backend=backend)

    def to_obscollection(
        self, entity: Literal["GLD", "GAR"] = "GLD", name: str = ""
    ) -> ObsCollection:
        """Convert BronFormat data to a HydroPandas ObsCollection.

        Parameters
        ----------
        entity : Literal["GLD", "GAR"], optional
            The entity type to convert (e.g., "GLD" for groundwater, "GAR"
            for water quality). By default "GLD".
        name : str, optional
            Name for the ObsCollection, by default "".

        Returns
        -------
        ObsCollection
            A HydroPandas ObsCollection built from the data.

        Raises
        ------
        ValueError
            If the specified entity is not supported.
        ImportError
            If hydropandas is not installed.
        """
        from brofopy.ext.hpd import to_obscollection as _to_obscollection

        return _to_obscollection(self, entity=entity, name=name)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert BronFormat data to a pandas DataFrame.

        Flattens the nested structure into a DataFrame with time series measurements.
        MATLAB datetimes are converted to pandas Timestamps.

        Returns
        -------
        pd.DataFrame
            DataFrame with MultiIndex (Entity, BROID) and columns for DateTime,
            RawValue, and other measurement fields.
        """
        from brofopy.ext.pd import to_dataframe as _to_dataframe

        return _to_dataframe(self)
