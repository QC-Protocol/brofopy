"""Reader module for Bronformat files."""

from logging import getLogger
from pathlib import Path
from typing import Any, Callable, Literal, TypeAlias

import h5py as h5py
import numpy as np
import pandas as pd
import scipy as scipy

from brofopy.exceptions import BronformatParseError

logger = getLogger(__name__)

# Type aliases for numpy types
NpScalar: TypeAlias = Any  # Scalar extracted from numpy array
NpStructuredArray: TypeAlias = np.ndarray  # Structured numpy array (np.void)
NpStructuredItem: TypeAlias = np.void  # Single structured array item

# Type aliases for bronformat entities
EntityType = Literal[
    "GMN", "GMW", "GLD", "GAR", "Proces", "IN", "QC", "File", "GIS", "Cache"
]
SubEntityType = Literal[
    "Adm",
    "History",
    "Tube",
    "Well",
    "Dossier",
    "Source",
    "Point",
    "Shape",
    "Transect",
    "Hist",
    "GLD",
]

DEFAULT_COLUMNS_METADATA: list[str] = [
    "Entity",
    "BROID",
    "SubEntity",
]
DEFAULT_COLUMNS_DATA: list[str] = ["Entity", "BROID", "DateTime", "RawValue"]


def _extract_scalar(value: Any) -> NpScalar | None:
    """Extract scalar value from numpy array or return as-is.

    Parameters
    ----------
    value : Any
        The value to extract from. Can be a numpy array or scalar.

    Returns
    -------
    NpScalar | None
        Scalar value, or None if array is empty.
    """
    if isinstance(value, np.ndarray):
        if value.size == 1:
            result = value.flat[0]
            # Convert numpy scalars to Python types
            if isinstance(result, np.generic):
                return result.item()
            return result
        elif value.size == 0:
            return None
    return value


def _convert_matlab_datetime(value: int | float | np.number) -> pd.Timestamp | Any:
    """Convert MATLAB datenum (serial date) to pandas Timestamp.

    MATLAB's datenum format counts days since 0000-12-31 (day 0 = 0000-12-31,
    day 1 = 0001-01-01). For modern dates, we use a reference point to avoid
    overflow issues with pandas' nanosecond precision.

    Parameters
    ----------
    value : Any
        The MATLAB datetime value to convert.

    Returns
    -------
    Any
        pandas Timestamp if value is a MATLAB datetime, otherwise unchanged.
    """
    MATLAB_DATENUM_REFERENCE = 719529  # MATLAB datenum for 1970-01-01
    if isinstance(value, (int, float, np.number)):
        try:
            days_since_1970 = float(value) - MATLAB_DATENUM_REFERENCE
            return pd.Timestamp("1970-01-01") + pd.Timedelta(days=days_since_1970)
        except (ValueError, TypeError, OverflowError):
            return value
    return value


def _flatten_structured_item(
    item: Any, prefix: str = "", max_depth: int = 5
) -> dict[str, NpScalar | None]:
    """Recursively flatten a NumPy structured array item into a dictionary.

    Parameters
    ----------
    item : Any
        The structured array item to flatten.
    prefix : str
        Prefix to prepend to field names (for nested structures).
    max_depth : int
        Maximum recursion depth to prevent infinite loops.

    Returns
    -------
    dict[str, Any]
        Dictionary with flattened field names as keys.
    """
    if max_depth <= 0:
        return {}

    result = {}

    if not isinstance(item, np.void):
        # Not a structured array - return scalar
        scalar = _extract_scalar(item)
        if prefix:
            result[prefix] = scalar
        return result

    for field_name in item.dtype.names:
        field_data = item[field_name]
        new_prefix = f"{prefix}.{field_name}" if prefix else field_name

        # Check if this field is itself a structured array
        if isinstance(field_data, np.void):
            # Single structured item - recurse
            result.update(
                _flatten_structured_item(field_data, new_prefix, max_depth - 1)
            )
        elif isinstance(field_data, np.ndarray):
            if field_data.size == 0:
                result[new_prefix] = None
            elif field_data.size == 1 and isinstance(field_data.flat[0], np.void):
                # Single nested structured item
                result.update(
                    _flatten_structured_item(
                        field_data.flat[0], new_prefix, max_depth - 1
                    )
                )
            elif hasattr(field_data.dtype, "names") and field_data.dtype.names:
                # Array of structured items - flatten first element only to avoid lists
                if field_data.size > 0:
                    result.update(
                        _flatten_structured_item(
                            field_data.flat[0], new_prefix, max_depth - 1
                        )
                    )
            else:
                # Regular numpy array - extract scalar
                scalar = _extract_scalar(field_data)
                result[new_prefix] = scalar
        else:
            result[new_prefix] = _extract_scalar(field_data)

    return result


def _convert_datetime_values(flat_data: dict[str, Any]) -> dict[str, Any]:
    """Convert datetime-like values in a dictionary to pandas Timestamps.

    Parameters
    ----------
    flat_data : dict[str, Any]
        Dictionary with potentially datetime values.

    Returns
    -------
    dict[str, Any]
        Dictionary with datetime values converted to pandas Timestamps.
    """
    for key, val in flat_data.items():
        if "DateTime" in key or "Date" in key or "Time" in key:
            flat_data[key] = _convert_matlab_datetime(val)
    return flat_data


def _parse_measurements(measurements_arr: NpStructuredArray) -> pd.DataFrame:
    """Parse Measurements structured array into a DataFrame.

    Parameters
    ----------
    measurements_arr : np.ndarray
        Structured array with DateTime and RawValue fields.

    Returns
    -------
    pd.DataFrame
        DataFrame with DateTime and RawValue columns.
    """
    if measurements_arr.size == 0:
        return pd.DataFrame(columns=["DateTime", "RawValue"])

    datetimes = []
    rawvalues = []

    for meas in measurements_arr.flat:
        dt_scalar = _extract_scalar(meas["DateTime"])
        rv_scalar = _extract_scalar(meas["RawValue"])
        datetimes.append(_convert_matlab_datetime(dt_scalar))
        rawvalues.append(rv_scalar)

    return pd.DataFrame({"DateTime": datetimes, "RawValue": rawvalues})


def _create_empty_result_dfs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create empty metadata and data DataFrames with proper structure."""
    metadata_df = _create_metadata_df([])
    data_df = _create_data_df([])
    return metadata_df, data_df


def _create_metadata_df(metadata_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Create a metadata DataFrame from rows."""
    if not metadata_rows:
        return pd.DataFrame(columns=DEFAULT_COLUMNS_METADATA).set_index(
            DEFAULT_COLUMNS_METADATA
        )
    metadata_df = pd.DataFrame(metadata_rows)
    return metadata_df.set_index(DEFAULT_COLUMNS_METADATA)


def _create_data_df(data_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Create a data DataFrame from rows."""
    if not data_rows:
        return pd.DataFrame(columns=DEFAULT_COLUMNS_DATA).set_index(["Entity", "BROID"])
    data_df = pd.DataFrame(data_rows)
    return data_df.set_index(["Entity", "BROID"])


def _build_metadata_row(
    broid: NpScalar | None,
    entity_name: EntityType,
    entity_id: NpScalar | None,
    sub_entity: SubEntityType,
    sub_idx: int,
    **extra_fields: Any,
) -> dict[str, Any]:
    """Build a metadata row dictionary."""
    return {
        "BROID": broid,
        "Entity": entity_name,
        "EntityID": np.nan if entity_id is None else entity_id,
        "SubEntity": sub_entity,
        "SubEntityID": sub_idx,
        **extra_fields,
    }


def _get_entity_id_broid(
    entity: NpStructuredItem, id_field: str | None = None
) -> tuple[NpScalar | None, NpScalar | None]:
    """Extract entity ID and BROID from Adm field.

    Parameters
    ----------
    entity : np.void
        The structured entity to extract IDs from.
    id_field : str | None
        Name of the ID field in the Adm sub-structure.

    Returns
    -------
    tuple[Any, Any]
        (entity_id, broid) - extracted ID and BROID values.
    """
    entity_id = None
    broid = None
    if "Adm" in entity.dtype.names:
        adm = entity["Adm"]
        if adm.size > 0:
            adm_item = adm.flat[0]
            if isinstance(adm_item, np.void):
                if id_field and id_field in adm_item.dtype.names:
                    entity_id = _extract_scalar(adm_item[id_field])
                if "BROID" in adm_item.dtype.names:
                    broid = _extract_scalar(adm_item["BROID"])
    return entity_id, broid


def _parse_entity_array(
    entity_arr: NpStructuredArray, entity_name: EntityType, id_field: str | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parser for entity arrays with nested structured fields.

    Parameters
    ----------
    entity_arr : np.ndarray
        The structured array to parse.
    entity_name : EntityType
        Name of the entity (e.g., 'GMW', 'GLD').
    id_field : str | None
        Name of the ID field in the entity's Adm sub-structure.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - metadata DataFrame and empty data DataFrame for the entity.
    """
    logger.debug(f"Parsing {entity_arr.size} {entity_name} items")
    metadata_rows: list[dict[str, Any]] = []

    if entity_arr.size == 0:
        logger.debug(f"  {entity_name}: empty array")
        return _create_empty_result_dfs()

    for _, entity in enumerate(entity_arr.flat):
        # Get entity ID and BROID
        entity_id: NpScalar | None
        broid: NpScalar | None
        entity_id, broid = _get_entity_id_broid(entity, id_field)

        # Process each field of the entity
        for field_name in entity.dtype.names:
            field_data = entity[field_name]

            if isinstance(field_data, np.ndarray) and field_data.size > 0:
                # Check if this is a structured array
                if hasattr(field_data.dtype, "names") and field_data.dtype.names:
                    sub_entity_name: SubEntityType = field_name

                    for sub_idx, sub_entity in enumerate(field_data.flat):
                        # Flatten the sub-entity
                        flat_data = _flatten_structured_item(sub_entity)
                        flat_data = _convert_datetime_values(flat_data)

                        metadata_row = _build_metadata_row(
                            broid,
                            entity_name,
                            entity_id,
                            sub_entity_name,
                            sub_idx,
                            **flat_data,
                        )
                        metadata_rows.append(metadata_row)
                else:
                    # Simple array field
                    flat_value = _extract_scalar(field_data)
                    metadata_row = _build_metadata_row(
                        broid,
                        entity_name,
                        entity_id,
                        field_name,
                        0,
                        Value=flat_value,
                    )
                    metadata_rows.append(metadata_row)
            else:
                # Empty or scalar field
                flat_value = _extract_scalar(field_data)
                metadata_row = _build_metadata_row(
                    broid,
                    entity_name,
                    entity_id,
                    field_name,
                    0,
                    Value=flat_value,
                )
                metadata_rows.append(metadata_row)

    metadata_df = _create_metadata_df(metadata_rows)
    data_df = pd.DataFrame(columns=DEFAULT_COLUMNS_DATA).set_index(["Entity", "BROID"])
    return metadata_df, data_df


def _parse_gmw(gmw_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse GMW (Groundwater Monitoring Wells) array."""
    return _parse_entity_array(gmw_arr, "GMW", "GMWID")


def _parse_gld(gld_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse GLD (Groundwater Level Data) array with special handling for Measurements.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - metadata and time series measurements DataFrames.
    """
    logger.debug(f"Parsing {gld_arr.size} GLD items")
    metadata_rows: list[dict[str, Any]] = []
    data_rows: list[dict[str, Any]] = []

    if gld_arr.size == 0:
        logger.debug("  GLD: empty array")
        return _create_empty_result_dfs()

    for gld in gld_arr.flat:
        # Get GLDID and BROID from Adm
        gld_id: NpScalar | None
        broid: NpScalar | None
        gld_id, broid = _get_entity_id_broid(gld, "GLDID")

        # Process each field
        for field_name in gld.dtype.names:
            field_data = gld[field_name]
            sub_entity_name: SubEntityType = field_name

            if isinstance(field_data, np.ndarray) and field_data.size > 0:
                for sub_idx, sub_entity in enumerate(field_data.flat):
                    # Don't flatten yet - check for Measurements first
                    flat_data = _flatten_structured_item(sub_entity)
                    flat_data = _convert_datetime_values(flat_data)

                    # Special handling for Source sub-entity with Measurements
                    # Check if the raw sub_entity has a Measurements field that is an array
                    if sub_entity_name == "Source" and isinstance(sub_entity, np.void):
                        if "Measurements" in sub_entity.dtype.names:
                            measurements_arr = sub_entity["Measurements"]
                            if (
                                isinstance(measurements_arr, np.ndarray)
                                and measurements_arr.size > 0
                            ):
                                logger.debug(
                                    f"  Found {measurements_arr.size} measurements in Source"
                                )
                                # Parse measurements using helper
                                meas_df = _parse_measurements(measurements_arr)
                                for _, row in meas_df.iterrows():
                                    data_rows.append(
                                        {
                                            "Entity": "GLD",
                                            "BROID": broid,
                                            "DateTime": row["DateTime"],
                                            "RawValue": row["RawValue"],
                                        }
                                    )
                                logger.debug(f"  Added {len(meas_df)} measurement rows")

                    # Add the metadata row (without Measurements to avoid duplication)
                    # Remove Measurements fields from flat_data for metadata row
                    flat_data_metadata = {
                        k: v
                        for k, v in flat_data.items()
                        if not k.startswith("Measurements.")
                        and not k.startswith("DateTime")
                        and not k.startswith("RawValue")
                    }

                    metadata_row = _build_metadata_row(
                        broid,
                        "GLD",
                        gld_id,
                        sub_entity_name,
                        sub_idx,
                        **flat_data_metadata,
                    )
                    metadata_rows.append(metadata_row)

    metadata_df = _create_metadata_df(metadata_rows)
    data_df = _create_data_df(data_rows)
    return metadata_df, data_df


def _parse_gmn(gmn_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse GMN (Groundwater Monitoring Network) array."""
    return _parse_entity_array(gmn_arr, "GMN", "GMNID")


def _parse_gar(gar_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse GAR (Groundwater Analysis Results) array."""
    return _parse_entity_array(gar_arr, "GAR")


def _parse_proces(proces_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse Proces array."""
    return _parse_entity_array(proces_arr, "Proces", "ProcessID")


def _parse_in(in_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse IN (Instrument) array."""
    return _parse_entity_array(in_arr, "IN", "ID")


def _parse_qc(qc_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse QC (Quality Control) array."""
    return _parse_entity_array(qc_arr, "QC")


def _parse_file(file_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse File array."""
    return _parse_entity_array(file_arr, "File")


def _parse_gis(gis_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse GIS array."""
    return _parse_entity_array(gis_arr, "GIS")


def _parse_cache(cache_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse Cache array."""
    return _parse_entity_array(cache_arr, "Cache")


def _check_extension(filepath: str | Path) -> None:
    """Check if the file has the expected extension.

    Parameters
    ----------
    filepath : str or Path
        The path to the file to check.

    Raises
    ------
    BronformatParseError
        If the file has the legacy .bron extension.
    AssertionError
        If the file does not have the expected .bron2 extension.
    """
    extension_accepted = ".bron2"
    extension = Path(filepath).suffix
    logger.debug(f"Checking file extension: {extension}")

    if extension == ".bron":
        logger.warning("Legacy .bron extension detected - not supported")
        raise BronformatParseError(
            "The .bron extension is not supported. Please convert your file to .bron2 format. "
            "The .bron extension could maybe be supported in the future. But it would require"
            " more work investigating scipy.io.matlab MatlabOpaque and MatlabObject types."
        )
    assert extension == extension_accepted, (
        f"File must have {extension_accepted} extension, got {extension}"
    )
    logger.debug("File extension validated: .bron2")


def read_bronformat(
    filepath: str | Path, backend: Literal["scipy", "h5py"] = "scipy"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read a Bronformat file and return metadata and data as separate DataFrames.

    Note on MATLAB .mat versions:
    - Files saved as < v7.3 use a proprietary binary format and are supported
      by the 'scipy' backend. This is currently the only supported format.
    - Files saved as v7.3 or higher use the HDF5 standard and require the 'h5py'
      backend, which is reserved for future implementation.

    Parameters
    ----------
    filepath : str or Path
        Path to the Bronformat file to read.
    backend : Literal["scipy", "h5py"], optional
        The backend to use for reading the file. Use 'scipy' for files < v7.3
        and 'h5py' for v7.3+ (HDF5) files. By default "scipy".

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - Two DataFrames:
        - metadata_df: Contains all administrative and configuration data with MultiIndex
          (Entity, BROID, SubEntity) and columns (EntityID, SubEntityID)
        - data_df: Contains time series measurements with index (Entity, BROID) and columns (DateTime, RawValue)

    Raises
    ------
    ValueError
        If the backend is not supported.
    """
    if backend == "scipy":
        return read_bronformat_scipy(filepath)
    elif backend == "h5py":
        return read_bronformat_h5py(filepath)
    else:
        raise ValueError(
            "Invalid backend. Choose 'scipy' (for < v7.3) or 'h5py' (for >= v7.3)."
        )


def read_bronformat_scipy(filepath: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read a Bronformat file (< v7.3) using SciPy and return two DataFrames.

    SciPy natively supports reading MATLAB files up to version 7.2. If the
    Bronformat file was saved as v7.3 or higher (HDF5), SciPy will raise a
    NotImplementedError.

    Parameters
    ----------
    filepath : str or Path
        Path to the Bronformat file to read.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - Two DataFrames with metadata and time series data.

    Raises
    ------
    BronformatParseError
        If the file cannot be parsed as a valid Bronformat or if it's an HDF5 file.

    Examples
    --------
    >>> metadata, data = read_bronformat("sample.bron2", backend="scipy")
    >>> isinstance(metadata, pd.DataFrame)
    True
    >>> isinstance(data, pd.DataFrame)
    True
    """
    _check_extension(filepath)
    logger.info(f"Loading Bronformat file: {filepath}")

    try:
        io = scipy.io.loadmat(filepath)
    except NotImplementedError as e:
        logger.error("HDF5 file detected - scipy backend cannot handle v7.3+ files")
        raise BronformatParseError(
            "Detected a v7.3+ (HDF5) file. The 'scipy' backend only supports "
            "MATLAB files < v7.3. Please use the 'h5py' backend (when implemented) "
            "or re-save your file in an older format."
        ) from e

    logger.debug(f"Loaded {len(io)} top-level keys from file")
    return parse_bronformat_scipy(io)


def parse_bronformat_scipy(d: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse the dictionary loaded from a < v7.3 Bronformat file into DataFrames.

    Notes
    -----
    A bronformat file is basically a MATLAB .mat file, but with a specific
    structure. SciPy handles the proprietary binary formats (< v7.3) well.
    However, extracting the relevant information from the nested dictionary
    into a structured DataFrame requires custom parsing logic.

    Parameters
    ----------
    d : dict
        The dictionary returned by scipy.io.loadmat when reading a Bronformat file.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - Two DataFrames:
        - metadata_df: Contains all administrative and configuration data with MultiIndex
        - data_df: Contains time series measurements (DateTime, RawValue, BROID, ObservationID)
    """
    # Parse each entity type separately
    all_metadata_dfs = []
    all_data_dfs = []

    entity_parsers: dict[
        EntityType, Callable[[NpStructuredArray], tuple[pd.DataFrame, pd.DataFrame]]
    ] = {
        "GMN": _parse_gmn,
        "GMW": _parse_gmw,
        "GLD": _parse_gld,
        "GAR": _parse_gar,
        "Proces": _parse_proces,
        "IN": _parse_in,
        "QC": _parse_qc,
        "File": _parse_file,
        "GIS": _parse_gis,
        "Cache": _parse_cache,
    }

    # Log which entities are present in the file
    available_entities = [k for k in entity_parsers.keys() if k in d]
    missing_entities = [k for k in entity_parsers.keys() if k not in d]
    logger.info(f"Found entities: {available_entities}")
    logger.debug(f"Missing entities: {missing_entities}")

    for entity_name, parser in entity_parsers.items():
        if entity_name in d:
            entity_arr = d[entity_name]
            logger.debug(f"Parsing {entity_name} with {len(entity_arr)} items")
            if isinstance(entity_arr, np.ndarray):
                try:
                    metadata_df, data_df = parser(entity_arr)
                    if not metadata_df.empty:
                        logger.debug(
                            f"  {entity_name}: {len(metadata_df)} metadata rows"
                        )
                        all_metadata_dfs.append(metadata_df)
                    else:
                        logger.debug(f"  {entity_name}: empty metadata")
                    if not data_df.empty:
                        logger.debug(f"  {entity_name}: {len(data_df)} data rows")
                        all_data_dfs.append(data_df)
                    else:
                        logger.debug(f"  {entity_name}: empty data")
                except Exception as e:
                    # Log error but continue with other entities
                    logger.error(f"Failed to parse {entity_name}: {e}")
                    import warnings

                    warnings.warn(f"Failed to parse {entity_name}: {e}")

    # Concatenate all metadata DataFrames
    if not all_metadata_dfs:
        metadata_df = pd.DataFrame(columns=DEFAULT_COLUMNS_METADATA).set_index(
            DEFAULT_COLUMNS_METADATA
        )
    else:
        metadata_df = pd.concat(all_metadata_dfs)
        for col in list(metadata_df.columns):
            non_null = metadata_df[col].dropna()
            if non_null.size > 0 and isinstance(non_null.iloc[0], np.ndarray):
                metadata_df = metadata_df.drop(columns=[col])
        metadata_df = metadata_df.sort_index()

    # Concatenate all data DataFrames
    data_df = (
        pd.concat(all_data_dfs).sort_index()
        if all_data_dfs
        else pd.DataFrame(columns=DEFAULT_COLUMNS_DATA).set_index(["Entity", "BROID"])
    )

    logger.info(
        f"Parsing complete: {len(metadata_df)} metadata rows, {len(data_df)} data rows"
    )
    return metadata_df, data_df


def read_bronformat_h5py(filepath: str | Path) -> pd.DataFrame:
    """Read a Bronformat (*.bron2) file (v7.3+) using h5py and return a DataFrame.

    Starting with MATLAB v7.3, .mat files are built on the HDF5 standard.
    Because SciPy cannot read these, h5py is required. This functionality
    is a placeholder for future implementation.

    Parameters
    ----------
    filepath : str or Path
        Path to the Bronformat file to read.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the data from the Bronformat file.

    Raises
    ------
    BronformatParseError
        Currently always raised, as HDF5 parsing is not yet implemented.
    """
    _check_extension(filepath)

    raise BronformatParseError(
        "Reading v7.3+ (HDF5) Bronformat files via h5py is not yet implemented. "
        "Currently, only .mat formats < v7.3 are supported via the default scipy backend."
    )

    # Unreachable code kept for future structural reference
    io = h5py.File(filepath, "r")
    return parse_bronformat_h5py(io)


def parse_bronformat_h5py(d: dict[str, Any]) -> pd.DataFrame:
    """Parse the h5py File object loaded from a v7.3+ Bronformat file.

    Parameters
    ----------
    d : dict or h5py.File
        The HDF5 object returned by h5py when reading a v7.3+ Bronformat file.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the parsed data from the Bronformat file.

    Raises
    ------
    BronformatParseError
        Currently always raised, as parsing logic is not implemented.
    """
    raise BronformatParseError(
        "Parsing of v7.3+ Bronformat files via h5py is not yet implemented."
    )


if __name__ == "__main__":
    import logging
    from pathlib import Path

    logging.basicConfig(level=logging.DEBUG)  # or INFO for less verbose output
    # Try to find the test data file
    test_path = Path.cwd().parent.parent / "tests/data/testdata.bron2"

    metadata, data = read_bronformat(test_path, backend="scipy")

    # print("=== METADATA ===")
    # print(metadata)
    # print()
    # print("=== DATA ===")
    # print(data.head())
    # print(f"Total measurements: {len(data)}")
