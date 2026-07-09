"""BronFormat data structure module.

Provides a hierarchical structure for Bronformat data that mirrors the HDF5 file structure:
- BronFormat is the root container with entity types as attributes
- Each entity is a dict of entries (keyed by BROID/ID)
- Each entry contains groups (sub-entities like Adm, Dossier, Source, etc.)
- Each group contains the actual data as dictionaries
- Time series data is kept as raw arrays/dicts, not DataFrames
  (DataFrames are only created when needed for specific operations)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd


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

    GMN: Optional[dict[str, Any]] = None
    GMW: Optional[dict[str, Any]] = None
    GLD: Optional[dict[str, Any]] = None
    GAR: Optional[dict[str, Any]] = None
    BHR: Optional[dict[str, Any]] = None
    GUF: Optional[dict[str, Any]] = None
    GPD: Optional[dict[str, Any]] = None
    Proces: Optional[dict[str, Any]] = None
    IN: Optional[dict[str, Any]] = None
    QC: Optional[dict[str, Any]] = None
    File: Optional[dict[str, Any]] = None
    GIS: Optional[dict[str, Any]] = None
    Cache: Optional[dict[str, Any]] = None
    SAD: Optional[dict[str, Any]] = None

    def __repr__(self) -> str:
        """Representation of the BronFormat object."""
        entities = [name for name, val in self.__dict__.items() if val is not None]
        return f"BronFormat({', '.join(entities)})"

    def to_dict(self) -> dict[str, Any]:
        """Convert entire structure to nested dictionary."""
        return {name: val for name, val in self.__dict__.items() if val is not None}

    def print(self, indent: int = 0) -> None:
        """Pretty print the structure."""
        prefix = "  " * indent
        for name, val in self.__dict__.items():
            if val is None:
                continue
            print(f"{prefix}{name}/ (group)")
            _print_dict(val, indent + 1)


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


def _get_entity_id_from_row(row: pd.Series, entity_name: str) -> str | None:
    """Extract an ID from a row, trying various ID columns."""
    # Try EntityID
    if "EntityID" in row.index and pd.notna(row["EntityID"]):
        return str(row["EntityID"])

    # Try entity-specific ID
    entity_id_col = f"{entity_name}ID"
    if entity_id_col in row.index and pd.notna(row[entity_id_col]):
        return str(row[entity_id_col])

    # Try BROID
    if "BROID" in row.index and pd.notna(row["BROID"]):
        return str(row["BROID"])

    # Try to find any ID column
    for col in row.index:
        if "ID" in col and pd.notna(row[col]):
            return str(row[col])

    return None


def _convert_from_dataframes(
    metadata_df: pd.DataFrame, data_df: pd.DataFrame
) -> BronFormat:
    """Convert DataFrame output to BronFormat structure with nested dicts."""
    result = BronFormat()

    # Define entity types
    entity_types = [
        "GMN",
        "GMW",
        "GLD",
        "GAR",
        "BHR",
        "GUF",
        "GPD",
        "Proces",
        "IN",
        "QC",
        "File",
        "GIS",
        "Cache",
        "SAD",
    ]

    # Group metadata by Entity and BROID
    for entity_name in entity_types:
        if entity_name not in metadata_df.index.get_level_values("Entity").unique():
            continue

        entity_metadata = metadata_df.xs(entity_name, level="Entity")
        entity_dict: dict[str, dict[str, Any]] = {}

        # Check if we have BROID values or if they're all NaN
        broid_values = entity_metadata.index.get_level_values("BROID")
        all_broid_nan = broid_values.isna().all()

        if all_broid_nan:
            # When all BROIDs are NaN, group by SubEntity and try to extract ID from columns
            for sub_entity, sub_group in entity_metadata.groupby(level="SubEntity"):
                entry_id = None
                for _, row in sub_group.iterrows():
                    entry_id = _get_entity_id_from_row(row, entity_name)
                    if entry_id:
                        break

                if entry_id is None:
                    continue

                if entry_id not in entity_dict:
                    entity_dict[entry_id] = {}

                # Create sub-entity dict (even if empty)
                if sub_entity not in entity_dict[entry_id]:
                    entity_dict[entry_id][sub_entity] = {}

                # Add all columns as key-value pairs
                # Exclude internal columns (EntityID, SubEntityID)
                internal_cols = {"EntityID", "SubEntityID"}
                for _, row in sub_group.iterrows():
                    for col in sub_group.columns:
                        if col in internal_cols:
                            continue
                        val = row[col]
                        if pd.notna(val):
                            entity_dict[entry_id][sub_entity][col] = val
        else:
            # Group by BROID
            for broid, group in entity_metadata.groupby(level="BROID", dropna=False):
                if pd.isna(broid):
                    continue

                broid_str = str(broid)
                if broid_str not in entity_dict:
                    entity_dict[broid_str] = {}

                # Group by SubEntity
                for sub_entity, sub_group in group.groupby(level="SubEntity"):
                    # Create sub-entity dict (even if empty)
                    if sub_entity not in entity_dict[broid_str]:
                        entity_dict[broid_str][sub_entity] = {}

                    # Add all columns as key-value pairs
                    # Exclude internal columns (EntityID, SubEntityID)
                    internal_cols = {"EntityID", "SubEntityID"}
                    for _, row in sub_group.iterrows():
                        for col in sub_group.columns:
                            if col in internal_cols:
                                continue
                            val = row[col]
                            if pd.notna(val):
                                entity_dict[broid_str][sub_entity][col] = val

        # Add time series data to Source/M measurements
        if entity_name in data_df.index.get_level_values("Entity").unique():
            entity_data = data_df.xs(entity_name, level="Entity")
            for broid, group in entity_data.groupby(level="BROID", dropna=False):
                if pd.isna(broid):
                    continue

                broid_str = str(broid)
                if broid_str not in entity_dict:
                    entity_dict[broid_str] = {}

                # Store time series in Source sub-entity as Measurements
                if "Source" not in entity_dict[broid_str]:
                    entity_dict[broid_str]["Source"] = {}

                # Convert to list of dicts
                ts_list = []
                for _, row in group.iterrows():
                    ts_row = {}
                    for col in group.columns:
                        ts_row[col] = row[col]
                    ts_list.append(ts_row)

                entity_dict[broid_str]["Source"]["Measurements"] = ts_list

        if entity_dict:
            setattr(result, entity_name, entity_dict)

    return result


def read_bronformat(filepath: str | Path) -> BronFormat:
    """Read Bronformat file and return BronFormat structure.

    The returned structure mirrors the HDF5 file structure:
    - BronFormat has entity types as attributes (GLD, GAR, BHR, etc.)
    - Each entity is a dict keyed by BROID/ID
    - Each entry has sub-entities (Adm, Dossier, Source, etc.) as dicts
    - Time series data is stored as list of dicts under "_timeseries" key

    Parameters
    ----------
    filepath : str or Path
        Path to .bron2, .bronx, or .hdf5 file.

    Returns
    -------
    BronFormat
        BronFormat object with entity types as attributes.
        Each entity contains nested dictionaries mirroring the HDF5 structure.

    Raises
    ------
    ValueError
        If file extension is not supported.
    BronformatParseError
        If file cannot be parsed.
    """
    from brofopy.exceptions import BronformatParseError
    from brofopy.reader import read_bronformat as read_bronformat_df

    filepath = Path(filepath)

    # Use existing reader to get DataFrames
    if filepath.suffix.lower() in (".hdf5", ".bronx"):
        metadata_df, data_df = read_bronformat_df(filepath, backend="h5py")
    elif filepath.suffix.lower() == ".bron":
        raise BronformatParseError(
            "The .bron extension is not supported. Please convert your file."
        )
    else:
        metadata_df, data_df = read_bronformat_df(filepath, backend="scipy")

    # Convert DataFrames to nested dict structure
    return _convert_from_dataframes(metadata_df, data_df)
