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
from typing import Any, Literal

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

    def to_dataframes(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Convert BronFormat structure to metadata and data DataFrames.

        This recreates the original DataFrame-based output format with:
        - metadata_df: Contains all administrative and configuration data with MultiIndex
          (Entity, BROID, SubEntity) and columns (EntityID, SubEntityID, ...)
        - data_df: Contains time series measurements with index (Entity, BROID) and columns
          (DateTime, RawValue, ...)

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            (metadata_df, data_df) - Two DataFrames matching the original format.
        """
        return _convert_to_dataframes(self)

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
        if (
            not data_df.empty
            and hasattr(data_df.index, "get_level_values")
            and "Entity" in data_df.index.names
        ):
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


def _convert_to_dataframes(bronformat: BronFormat) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert BronFormat structure back to metadata and data DataFrames.

    This is the reverse of _convert_from_dataframes and recreates the original
    DataFrame-based format.

    Parameters
    ----------
    bronformat : BronFormat
        The BronFormat object to convert.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - metadata and data DataFrames.
    """
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

    metadata_rows = []
    data_rows = []

    for entity_name in entity_types:
        entity_data = getattr(bronformat, entity_name, None)
        if entity_data is None:
            continue

        for entity_id, entry in entity_data.items():
            # Process metadata for each sub-entity
            for sub_entity_name, sub_entity_data in entry.items():
                if sub_entity_name == "Source" and "Measurements" in sub_entity_data:
                    # Handle time series data separately
                    measurements = sub_entity_data["Measurements"]
                    if isinstance(measurements, list):
                        for measurement in measurements:
                            data_row = {
                                "Entity": entity_name,
                                "BROID": entity_id,
                            }
                            for key, value in measurement.items():
                                data_row[key] = value
                            data_rows.append(data_row)
                    continue

                # Handle Volumes for GPD (treat as time series)
                if sub_entity_name == "Volumes" and entity_name == "GPD":
                    volumes = (
                        sub_entity_data["Volumes"]
                        if isinstance(sub_entity_data, dict)
                        else sub_entity_data
                    )
                    if isinstance(volumes, list):
                        for volume in volumes:
                            data_row = {
                                "Entity": entity_name,
                                "BROID": entity_id,
                            }
                            for key, value in volume.items():
                                data_row[key] = value
                            data_rows.append(data_row)
                    continue

                # Process metadata
                if isinstance(sub_entity_data, dict):
                    for field_name, field_value in sub_entity_data.items():
                        # Skip Measurements and Volumes as they're handled separately
                        if field_name in ("Measurements", "Volumes"):
                            continue

                        metadata_row = {
                            "Entity": entity_name,
                            "BROID": entity_id,
                            "SubEntity": sub_entity_name,
                            "EntityID": entity_id,
                            "SubEntityID": 0,
                        }
                        metadata_row[field_name] = field_value
                        metadata_rows.append(metadata_row)
                else:
                    # Simple field value
                    metadata_row = {
                        "Entity": entity_name,
                        "BROID": entity_id,
                        "SubEntity": sub_entity_name,
                        "EntityID": entity_id,
                        "SubEntityID": 0,
                        "Value": sub_entity_data,
                    }
                    metadata_rows.append(metadata_row)

    # Create DataFrames
    if metadata_rows:
        metadata_df = pd.DataFrame(metadata_rows)
        if not metadata_df.empty:
            metadata_df = metadata_df.set_index(["Entity", "BROID", "SubEntity"])
    else:
        metadata_df = pd.DataFrame(columns=["Entity", "BROID", "SubEntity"]).set_index(
            ["Entity", "BROID", "SubEntity"]
        )

    if data_rows:
        data_df = pd.DataFrame(data_rows)
        if (
            not data_df.empty
            and "Entity" in data_df.columns
            and "BROID" in data_df.columns
        ):
            data_df = data_df.set_index(["Entity", "BROID"])
        else:
            data_df = pd.DataFrame(
                columns=["Entity", "BROID", "DateTime", "RawValue"]
            ).set_index(["Entity", "BROID"])
    else:
        data_df = pd.DataFrame(
            columns=["Entity", "BROID", "DateTime", "RawValue"]
        ).set_index(["Entity", "BROID"])

    return metadata_df, data_df


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
