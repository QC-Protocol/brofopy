"""Reader module for Bronformat files."""

from logging import getLogger
from pathlib import Path
from typing import Any, Callable, Literal, TypeAlias, cast

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
    "GMN",
    "GMW",
    "GLD",
    "GAR",
    "Proces",
    "IN",
    "QC",
    "File",
    "GIS",
    "Cache",
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
        if value.size == 0:
            return None
        # Extract first element for small arrays (treat as scalar)
        # This handles cases where HDF5 stores single values as 1D or 2D arrays
        if value.ndim == 1 and value.size == 1:
            result = value.flat[0]
        elif value.ndim == 2 and value.size == 1:
            result = value.flat[0]
        elif value.ndim == 1 and value.size > 1:
            # For 1D arrays with multiple elements, extract first element
            # This handles cases like Comment with shape (2,) where we want the first value
            result = value.flat[0]
        elif value.ndim == 2 and value.size > 1:
            # For 2D arrays with multiple elements, extract first element
            # This handles cases like TubeNo with shape (2, 1) where we want the first value
            result = value.flat[0]
        else:
            result = value.flat[0] if value.size == 1 else value

        # Convert numpy scalars to Python types
        if isinstance(result, np.generic):
            return result.item()
        return result
    return value


def _convert_matlab_datetime(
    value: int | float | np.number | None,
) -> pd.Timestamp | Any:
    """Convert MATLAB datenum (serial date) to pandas Timestamp.

    MATLAB's datenum format counts days since 0000-12-31 (day 0 = 0000-12-31,
    day 1 = 0001-01-01). For modern dates, we use a reference point to avoid
    overflow issues with pandas' nanosecond precision.

    Parameters
    ----------
    value : int | float | np.number | None
        The MATLAB datetime value to convert.

    Returns
    -------
    pd.Timestamp | Any
        pandas Timestamp if value is a MATLAB datetime, otherwise unchanged.
    """
    if value is None:
        return None
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

    if item.dtype.names:
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
        Structured array with measurement fields (typically DateTime, RawValue,
        and potentially others like QC flags, observation IDs, etc.).

    Returns
    -------
    pd.DataFrame
        DataFrame with all measurement columns extracted from the structured array.
    """
    if measurements_arr.size == 0:
        if hasattr(measurements_arr.dtype, "names") and measurements_arr.dtype.names:
            return pd.DataFrame(
                columns=list(cast(tuple[str, ...], measurements_arr.dtype.names))
            )
        return pd.DataFrame(columns=["DateTime", "RawValue"])

    # Dynamically get all field names from the structured array
    if hasattr(measurements_arr.dtype, "names") and measurements_arr.dtype.names:
        field_names: list[str] = list(
            cast(tuple[str, ...], measurements_arr.dtype.names)
        )
    else:
        field_names = ["DateTime", "RawValue"]

    result = {name: [] for name in field_names}

    for meas in measurements_arr.flat:
        for field_name in field_names:
            value = _extract_scalar(meas[field_name])
            # Convert datetime-like fields
            if "DateTime" in field_name or "Date" in field_name or "Time" in field_name:
                value = _convert_matlab_datetime(value)
            result[field_name].append(value)

    return pd.DataFrame(result)


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
    if entity.dtype.names and "Adm" in entity.dtype.names:
        adm = entity["Adm"]
        if adm.size > 0:
            adm_item = adm.flat[0]
            if isinstance(adm_item, np.void):
                if (
                    id_field
                    and adm_item.dtype.names
                    and id_field in adm_item.dtype.names
                ):
                    entity_id = _extract_scalar(adm_item[id_field])
                if adm_item.dtype.names and "BROID" in adm_item.dtype.names:
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
        if entity.dtype.names:
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


def _parse_entity_with_measurements(
    entity_arr: NpStructuredArray,
    entity_name: EntityType,
    id_field: str | None,
    measurements_sub_entity: SubEntityType | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse entity array with special handling for Measurements sub-entities.

    This is a shared function for parsing entities like GLD and GAR that contain
    Measurements which should be extracted into the data DataFrame.

    Parameters
    ----------
    entity_arr : np.ndarray
        The structured array to parse.
    entity_name : str
        Name of the entity (e.g., 'GLD', 'GAR').
    id_field : str | None
        Name of the ID field in the entity's Adm sub-structure.
    measurements_sub_entity : str | None
        If specified, only check this sub-entity for Measurements.
        If None, check all sub-entities.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - metadata and measurements DataFrames.
    """
    logger.debug(f"Parsing {entity_arr.size} {entity_name} items")
    metadata_rows: list[dict[str, Any]] = []
    data_rows: list[dict[str, Any]] = []

    if entity_arr.size == 0:
        logger.debug(f"  {entity_name}: empty array")
        return _create_empty_result_dfs()

    for entity in entity_arr.flat:
        entity_id: NpScalar | None
        broid: NpScalar | None
        entity_id, broid = _get_entity_id_broid(entity, id_field)

        if entity.dtype.names:
            for field_name in entity.dtype.names:
                field_data = entity[field_name]
                sub_entity_name: SubEntityType = field_name

                if isinstance(field_data, np.ndarray) and field_data.size > 0:
                    for sub_idx, sub_entity in enumerate(field_data.flat):
                        flat_data = _flatten_structured_item(sub_entity)
                        flat_data = _convert_datetime_values(flat_data)

                        # Check if this sub-entity has Measurements
                        check_for_measurements = (
                            measurements_sub_entity is None
                            and isinstance(sub_entity, np.void)
                            and sub_entity.dtype.names
                            and "Measurements" in sub_entity.dtype.names
                        ) or (sub_entity_name == measurements_sub_entity)

                        if check_for_measurements and isinstance(sub_entity, np.void):
                            if (
                                sub_entity.dtype.names
                                and "Measurements" in sub_entity.dtype.names
                            ):
                                measurements_arr = sub_entity["Measurements"]
                            if (
                                isinstance(measurements_arr, np.ndarray)
                                and measurements_arr.size > 0
                            ):
                                logger.debug(
                                    f"  Found {measurements_arr.size} measurements in {sub_entity_name}"
                                )
                                meas_df = _parse_measurements(measurements_arr)
                                for _, row in meas_df.iterrows():
                                    data_row = {"Entity": entity_name, "BROID": broid}
                                    for col in meas_df.columns:
                                        data_row[col] = row[col]
                                    data_rows.append(data_row)
                                logger.debug(f"  Added {len(meas_df)} measurement rows")

                                flat_data_metadata = {
                                    k: v
                                    for k, v in flat_data.items()
                                    if not k.startswith("Measurements.")
                                    and not k.startswith("DateTime")
                                    and not k.startswith("RawValue")
                                }
                                metadata_row = _build_metadata_row(
                                    broid,
                                    entity_name,
                                    entity_id,
                                    sub_entity_name,
                                    sub_idx,
                                    **flat_data_metadata,
                                )
                                metadata_rows.append(metadata_row)
                                continue

                    metadata_row = _build_metadata_row(
                        broid,
                        entity_name,
                        entity_id,
                        sub_entity_name,
                        sub_idx,
                        **flat_data,
                    )
                    metadata_rows.append(metadata_row)

    metadata_df = _create_metadata_df(metadata_rows)
    data_df = _create_data_df(data_rows)
    return metadata_df, data_df


def _parse_gld(gld_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse GLD (Groundwater Level Data) array with special handling for Measurements."""
    return _parse_entity_with_measurements(gld_arr, "GLD", "GLDID", "Source")


def _parse_gmn(gmn_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse GMN (Groundwater Monitoring Network) array."""
    return _parse_entity_array(gmn_arr, "GMN", "GMNID")


def _parse_gar(gar_arr: NpStructuredArray) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse GAR (Groundwater Analysis Results) array with special handling for Measurements."""
    return _parse_entity_with_measurements(gar_arr, "GAR", "GARID")


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
        If the file does not have the expected extension.
    """
    extensions_accepted = (
        ".bron2",
        ".bronx",
    )
    extension = Path(filepath).suffix
    logger.debug(f"Checking file extension: {extension}")

    if extension == ".bron":
        logger.warning("Legacy .bron extension detected - not supported")
        raise BronformatParseError(
            "The .bron extension is not supported. Please convert your file. "
            "The .bron extension could maybe be supported in the future. But it would require"
            " more work investigating scipy.io.matlab MatlabOpaque and MatlabObject types."
        )
    assert extension in extensions_accepted, (
        f"File must have {extensions_accepted} extension, got {extension}"
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


def _get_entity_parsers() -> dict[
    EntityType, Callable[[NpStructuredArray], tuple[pd.DataFrame, pd.DataFrame]]
]:
    """Get the dictionary of entity parsers.

    These parsers are shared between both scipy and h5py backends since they
    work on numpy structured arrays regardless of the source.
    """
    return {
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


def _parse_bronformat_common(
    entity_data: dict[str, Any],
    entity_parsers: dict[
        EntityType, Callable[[NpStructuredArray], tuple[pd.DataFrame, pd.DataFrame]]
    ],
    log_prefix: str = "Parsing",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Shared parsing by both scipy and h5py backends.

    This function takes a dictionary of entity data (where keys are entity names
    and values are numpy structured arrays) and parses them using the provided
    entity parsers. This allows both backends to share the same parsing logic.

    Parameters
    ----------
    entity_data : dict[str, Any]
        Dictionary mapping entity names to their structured array data.
    entity_parsers : dict[EntityType, Callable]
        Dictionary of entity parser functions.
    log_prefix : str
        Prefix for log messages (e.g., "Parsing" or "HDF5 parsing").

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - Parsed metadata and data DataFrames.
    """
    all_metadata_dfs = []
    all_data_dfs = []

    # Log which entities are present in the file
    available_entities = [k for k in entity_parsers.keys() if k in entity_data]
    missing_entities = [k for k in entity_parsers.keys() if k not in entity_data]
    logger.info(f"Found entities: {available_entities}")
    logger.debug(f"Missing entities: {missing_entities}")

    for entity_name, parser in entity_parsers.items():
        if entity_name in entity_data:
            entity_arr = entity_data[entity_name]
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
                    logger.error(f"Failed to parse {entity_name}: {e}")

    return _concatenate_results(all_metadata_dfs, all_data_dfs, log_prefix)


def _concatenate_results(
    all_metadata_dfs: list[pd.DataFrame],
    all_data_dfs: list[pd.DataFrame],
    log_prefix: str = "Parsing",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Concatenate all metadata and data DataFrames into final results."""
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
        f"{log_prefix} complete: {len(metadata_df)} metadata rows, {len(data_df)} data rows"
    )
    return metadata_df, data_df


def parse_bronformat_scipy(d: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse the dictionary loaded from a < v7.3 Bronformat file into DataFrames.

    Notes
    -----
    A bronformat file is basically a MATLAB .mat file, but with a specific
    structure. SciPy handles the proprietary binary formats (< v7.3) well.
    However, extracting the relevant information from the nested dictionary
    into a structured DataFrame requires custom parsing logic.

    This function now uses the shared _parse_bronformat_common function to
    maximize code reuse with the h5py backend.

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
    entity_parsers = _get_entity_parsers()
    return _parse_bronformat_common(d, entity_parsers, "Parsing")


def _extract_measurements_from_h5py(
    dataset: h5py.Dataset, h5file: h5py.File
) -> np.ndarray:
    """Extract Measurements from HDF5 dataset with nested references.

    In HDF5 Bronformat files, Measurements are stored as:
    - A dataset with shape (1, N) containing references to measurement groups
    - Each measurement group has DateTime and RawValue datasets with shape (1, M)
      containing references to the actual numeric arrays
    - We need to flatten this to a structured array with N*M measurements

    Parameters
    ----------
    dataset : h5py.Dataset
        The Measurements dataset to extract from.
    h5file : h5py.File
        The HDF5 file object.

    Returns
    -------
    np.ndarray
        Structured array with DateTime and RawValue fields, one element per measurement.
    """
    data = dataset[()]

    # Collect all measurements
    all_dt_values = []
    all_rv_values = []

    # Iterate over all references in the dataset
    for ref in data.flat:
        if not isinstance(ref, h5py.h5r.Reference):
            continue

        # Dereference to get the measurement group
        meas_group = h5file[ref]
        if not isinstance(meas_group, h5py.Group):
            continue

        # Get DateTime dataset
        if "DateTime" in meas_group:
            dt_dataset = meas_group["DateTime"]
            dt_data = dt_dataset[()]

            # Dereference DateTime values
            for dt_ref in dt_data.flat:
                if isinstance(dt_ref, h5py.h5r.Reference):
                    dt_obj = h5file[dt_ref]
                    if isinstance(dt_obj, h5py.Dataset):
                        dt_array = dt_obj[()]
                        # Flatten and add all DateTime values
                        all_dt_values.extend(dt_array.flatten().tolist())
                elif isinstance(dt_ref, (int, float, np.number)):
                    all_dt_values.append(dt_ref)

        # Get RawValue dataset
        if "RawValue" in meas_group:
            rv_dataset = meas_group["RawValue"]
            rv_data = rv_dataset[()]

            # Dereference RawValue values
            for rv_ref in rv_data.flat:
                if isinstance(rv_ref, h5py.h5r.Reference):
                    rv_obj = h5file[rv_ref]
                    if isinstance(rv_obj, h5py.Dataset):
                        rv_array = rv_obj[()]
                        # Flatten and add all RawValue values
                        all_rv_values.extend(rv_array.flatten().tolist())
                elif isinstance(rv_ref, (int, float, np.number)):
                    all_rv_values.append(rv_ref)

    # Create structured array with one measurement per element
    if len(all_dt_values) == 0:
        return np.zeros(0, dtype=[("DateTime", object), ("RawValue", object)])

    # Ensure we have the same number of DateTime and RawValue elements
    min_length = min(len(all_dt_values), len(all_rv_values))
    all_dt_values = all_dt_values[:min_length]
    all_rv_values = all_rv_values[:min_length]

    # Create structured array
    arr = np.zeros(min_length, dtype=[("DateTime", object), ("RawValue", object)])
    for i in range(min_length):
        arr[i]["DateTime"] = all_dt_values[i]
        arr[i]["RawValue"] = all_rv_values[i]

    return arr


def _extract_h5py_dataset(
    dataset: h5py.Dataset, h5file: h5py.File | None = None
) -> Any:
    """Extract data from an HDF5 dataset, handling special cases."""
    data = dataset[()]

    # Handle character arrays - MATLAB stores strings as uint16 char codes
    if dataset.dtype == np.uint16:
        # Convert uint16 codes to characters
        chars = data.flatten().tolist()
        chars = [chr(c) for c in chars if c > 0]
        return "".join(chars) if chars else None

    # Handle other integer types that might be empty/zero character arrays
    # This can happen with malformed data where BROID is stored as uint64 [0, 0]
    if dataset.dtype in (np.uint8, np.uint32, np.uint64, np.int16, np.int32, np.int64):
        # If all values are zero, treat as empty string
        if np.all(data == 0):
            return None
        # Otherwise, try to interpret as character codes if values are valid
        try:
            chars = data.flatten().tolist()
            chars = [chr(c) for c in chars if c > 0]
            return "".join(chars) if chars else None
        except (ValueError, TypeError):
            # Not valid character codes, return as-is
            pass

    # Handle object dtype datasets that might contain references
    if dataset.dtype == object and h5file is not None and data.size > 0:
        # Check if it contains references
        first = data.flat[0]
        if isinstance(first, h5py.h5r.Reference):
            # Check if this is a Measurements dataset (special handling needed)
            first_obj = h5file[first]
            is_measurements = (
                isinstance(first_obj, h5py.Group)
                and "DateTime" in first_obj
                and "RawValue" in first_obj
            )

            if is_measurements:
                # Special handling for Measurements: flatten the nested structure
                return _extract_measurements_from_h5py(dataset, h5file)

            # This is a reference array - dereference all while preserving shape
            dereferenced = np.empty(data.shape, dtype=object)
            for idx in np.ndindex(data.shape):
                ref = data[idx]
                if isinstance(ref, h5py.h5r.Reference):
                    deref_obj = h5file[ref]
                    if isinstance(deref_obj, h5py.Group):
                        # Recursively convert group to dict then to structured array
                        nested_dict = _h5py_group_to_dict(deref_obj, h5file)
                        dereferenced[idx] = _dict_to_structured_array(nested_dict)
                    elif isinstance(deref_obj, h5py.Dataset):
                        dereferenced[idx] = _extract_h5py_dataset(deref_obj, h5file)
                    else:
                        dereferenced[idx] = ref
                else:
                    dereferenced[idx] = ref
            return dereferenced

    # Handle single-value numeric datasets
    if data.size == 1:
        return data.item()

    # Handle empty datasets
    if data.size == 0:
        return np.array([], dtype=object)

    # For numeric arrays, return as-is
    return data


def _h5py_group_to_dict(
    group: h5py.Group, h5file: h5py.File | None = None
) -> dict[str, Any]:
    """Convert an HDF5 group to a dictionary with values as numpy arrays or scalars.

    For nested groups, this recursively converts them to structured arrays to match
    the format that scipy.io.loadmat returns.
    """
    # If h5file is not provided, we can't dereference, so use parent file
    if h5file is None:
        # Find the file from the group
        h5file = group.file

    items = {}
    for key in group.keys():
        item = group[key]
        if isinstance(item, h5py.Dataset):
            items[key] = _extract_h5py_dataset(item, h5file)
        elif isinstance(item, h5py.Group):
            # Convert nested group to structured array
            nested_dict = _h5py_group_to_dict(item, h5file)
            items[key] = _dict_to_structured_array(nested_dict)
    return items


def _h5py_reference_to_dict(
    ref: h5py.h5r.Reference, h5file: h5py.File
) -> dict[str, Any]:
    """Dereference an HDF5 reference to a group and convert to dictionary."""
    obj = h5file[ref]
    if isinstance(obj, h5py.Group):
        return _h5py_group_to_dict(obj, h5file)
    elif isinstance(obj, h5py.Dataset):
        # Don't recursively dereference datasets - just extract the data
        return _extract_h5py_dataset(obj, h5file)
    return obj


def _extract_sub_entity_value(
    sub_obj: h5py.Dataset | h5py.Group,
    indices: tuple[int, ...],
    h5file: h5py.File,
) -> Any:
    """Extract a value from a sub-entity at the given indices.

    Handles both Dataset and Group sub-entities, with proper dereferencing
    of HDF5 references.
    """
    if isinstance(sub_obj, h5py.Dataset):
        if sub_obj.dtype == object:
            # This is a reference array - get the reference at indices
            data = sub_obj[()]
            if len(sub_obj.shape) == 2:
                # For 2D, use indices directly
                ref = data[indices] if len(indices) == 2 else data[indices[0]]
            else:
                # For 1D, use first index
                ref = data[indices[0]]

            if isinstance(ref, h5py.h5r.Reference):
                deref_data = _h5py_reference_to_dict(ref, h5file)
                return _dict_to_structured_array(deref_data)
            return ref
        else:
            # Non-object dataset - read directly
            return _extract_h5py_dataset(sub_obj, h5file)
    elif isinstance(sub_obj, h5py.Group):
        # Sub-entity is a group - convert to dict then structured array
        dict_data = _h5py_group_to_dict(sub_obj, h5file)
        return _dict_to_structured_array(dict_data)
    return None


def _extract_entity_data_from_h5py(
    h5file: h5py.File, entity_name: str
) -> NpStructuredArray | None:
    """Extract entity data from HDF5 file and convert to numpy structured array.

    This function handles the different ways entities can be stored in HDF5 format:
    1. As a group with sub-groups (e.g., GMN, IN)
    2. As a group with datasets containing references (e.g., GLD, GMW)
    3. As a simple dataset (e.g., GAR, GPD, GUF)

    Returns None if the entity cannot be extracted.
    """
    if entity_name not in h5file:
        return None

    entity_obj = h5file[entity_name]

    # Case 1: Entity is a dataset (might be references or simple values)
    if isinstance(entity_obj, h5py.Dataset):
        data = entity_obj[()]

        # If it's object dtype with references, dereference them
        if entity_obj.dtype == object and data.size > 0:
            first = data.flat[0]
            if isinstance(first, h5py.h5r.Reference):
                # This is an array of references to entity elements
                elements = []
                for ref in data.flat:
                    if isinstance(ref, h5py.h5r.Reference):
                        deref_data = _h5py_reference_to_dict(ref, h5file)
                        # Convert dict to structured array with one element
                        if isinstance(deref_data, dict):
                            elements.append(_dict_to_structured_array(deref_data))
                        else:
                            elements.append(deref_data)
                    else:
                        elements.append(ref)
                return np.array(elements, dtype=object).reshape(data.shape)

        # Simple dataset - return as-is
        return data

    # Case 2: Entity is a group
    if isinstance(entity_obj, h5py.Group):
        # Check if this group contains datasets with object dtype (references)
        has_ref_datasets = any(
            isinstance(entity_obj[k], h5py.Dataset) and entity_obj[k].dtype == object
            for k in entity_obj.keys()
        )

        if has_ref_datasets:
            # Entity has sub-entities as reference arrays (like GLD, GMW)
            sub_names = list(entity_obj.keys())

            # Get dimensions from first sub-entity dataset
            first_sub = entity_obj[sub_names[0]]
            if isinstance(first_sub, h5py.Dataset):
                # For reference arrays, the shape tells us the number of entities
                if len(first_sub.shape) == 2:
                    n_elements = first_sub.shape[1]  # GLD: (1, 25) means 25 entities
                    n_cols = first_sub.shape[0]  # GLD: 1 row
                else:
                    n_elements = first_sub.shape[0] if len(first_sub.shape) > 0 else 1
                    n_cols = 1
            else:
                n_elements = 1
                n_cols = 1

            # Create dtype for structured array
            dtype_list = [(name, object) for name in sub_names]

            # Create structured array to hold entity data
            # For GLD, we want shape (25,) not (1, 25) or (25, 1)
            if n_cols == 1 and n_elements > 1:
                # Flatten to (n_elements,) for entities like GLD
                arr = np.zeros(n_elements, dtype=dtype_list)
                for i in range(n_elements):
                    for sub_name in sub_names:
                        sub_obj = entity_obj[sub_name]
                        arr[i][sub_name] = _extract_sub_entity_value(
                            sub_obj, (0, i) if len(sub_obj.shape) == 2 else (i,), h5file
                        )
            else:
                # For entities with 2D layout
                arr = np.zeros((n_elements, n_cols), dtype=dtype_list)
                for i in range(n_elements):
                    for j in range(n_cols):
                        for sub_name in sub_names:
                            sub_obj = entity_obj[sub_name]
                            arr[i, j][sub_name] = _extract_sub_entity_value(
                                sub_obj, (i, j), h5file
                            )

            return arr
        else:
            # Entity is a group with sub-groups (like GMN, IN, Proces, QC)
            # Convert to structured array with one element
            dict_data = _h5py_group_to_dict(entity_obj, h5file)
            if dict_data:
                return _dict_to_structured_array(dict_data)

    return None


def _dict_to_structured_array(
    data_dict: dict[str, Any] | np.ndarray | Any,
) -> np.ndarray:
    """Convert a dictionary to a numpy structured array with one element.

    This creates a structured array that matches what scipy.io.loadmat returns
    for MATLAB struct arrays.
    """
    # Handle case where input is already an array
    if isinstance(data_dict, np.ndarray):
        return data_dict

    # Handle case where input is not a dict
    if not isinstance(data_dict, dict) or not data_dict:
        return np.array([data_dict] if data_dict is not None else [], dtype=object)

    # Build dtype - all fields are objects to handle nested structures
    dtype_list = [(key, object) for key in data_dict.keys()]

    # Create array with one element
    try:
        arr = np.zeros(1, dtype=dtype_list)
        for key, value in data_dict.items():
            arr[0][key] = value
        return arr
    except Exception:
        # If we can't create structured array, return the dict in an object array
        return np.array([data_dict], dtype=object)


def read_bronformat_h5py(filepath: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read a Bronformat (*.bronx) file (v7.3+) using h5py and return two DataFrames.

    Starting with MATLAB v7.3, .mat files are built on the HDF5 standard.
    This function reads HDF5-based Bronformat files and returns metadata and data
    DataFrames in the same format as the scipy backend.

    Parameters
    ----------
    filepath : str or Path
        Path to the Bronformat file to read.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - Two DataFrames:
        - metadata_df: Contains all administrative and configuration data with MultiIndex
          (Entity, BROID, SubEntity) and columns (EntityID, SubEntityID)
        - data_df: Contains time series measurements with index (Entity, BROID) and columns (DateTime, RawValue)

    Raises
    ------
    BronformatParseError
        If the file cannot be parsed as a valid Bronformat HDF5 file.
    """
    _check_extension(filepath)
    logger.info(f"Loading HDF5 Bronformat file: {filepath}")

    try:
        with h5py.File(filepath, "r") as h5file:
            return parse_bronformat_h5py(h5file)

    except NotImplementedError as e:
        logger.error("Unexpected NotImplementedError with h5py backend")
        raise BronformatParseError(f"Failed to read HDF5 file with h5py: {e}") from e
    except Exception as e:
        logger.error(f"Error reading HDF5 file: {e}")
        raise BronformatParseError(
            f"Failed to read HDF5 file with h5py backend: {e}"
        ) from e


def parse_bronformat_h5py(h5file: h5py.File) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse the h5py File object loaded from a v7.3+ Bronformat file.

    This function extracts entity data from the HDF5 file and parses it using
    the same parsing functions as the scipy backend, ensuring consistent behavior.

    This function now uses the shared _parse_bronformat_common function to
    maximize code reuse with the scipy backend.

    Parameters
    ----------
    h5file : h5py.File
        The HDF5 file object returned by h5py when reading a v7.3+ Bronformat file.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (metadata_df, data_df) - Two DataFrames with metadata and time series data.

    Raises
    ------
    BronformatParseError
        If the file cannot be parsed as a valid Bronformat.
    """
    logger.debug(f"Parsing HDF5 file, top-level keys: {list(h5file.keys())}")

    entity_parsers = _get_entity_parsers()

    # Extract entity data from HDF5 file
    entity_data = {}
    for entity_name in entity_parsers.keys():
        if entity_name in h5file:
            logger.debug(f"Extracting {entity_name} entity from HDF5")
            entity_arr = _extract_entity_data_from_h5py(h5file, entity_name)
            if entity_arr is not None:
                entity_data[entity_name] = entity_arr

    return _parse_bronformat_common(entity_data, entity_parsers, "HDF5 parsing")


if __name__ == "__main__":
    import logging
    from pathlib import Path

    logging.basicConfig(level=logging.DEBUG)  # or INFO for less verbose output
    # Try to find the test data file
    test_path = Path.cwd().parent.parent / "tests/data/testdata.bronx"

    metadata, data = read_bronformat(test_path, backend="h5py")
