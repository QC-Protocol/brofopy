"""Reader module for Bronformat files.

This module provides the core functionality to read Bronformat files
(.hdf5, .bronx, .bron2) and return a BronFormat object with nested
dictionaries that mirror the HDF5 file structure.

For HDF5 files (v7.3+), uses h5py backend.
For .bron2 files (< v7.3), uses scipy backend.
"""

from __future__ import annotations

from logging import getLogger
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import scipy

from brofopy.bronformat import BronFormat
from brofopy.exceptions import BronformatParseError

logger = getLogger(__name__)

ENTITY_TYPES = [
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


def _convert_to_python_types(value: Any) -> Any:
    """Convert numpy types to native Python types."""
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return None
        if value.dtype == np.uint16 and np.all(value == 0):
            return None
        if value.dtype in (np.uint16, np.uint8, np.int8, np.int16, np.int32, np.uint32):
            try:
                chars = value.flatten().tolist()
                chars = [chr(c) for c in chars if c > 0]
                if chars:
                    return "".join(chars)
                return None
            except (ValueError, TypeError):
                pass
        if value.size == 1:
            result = value.flat[0]
            if isinstance(result, np.generic):
                return result.item()
            return result
        return value.tolist()
    elif isinstance(value, np.generic):
        return value.item()
    elif isinstance(value, (list, tuple)):
        return [_convert_to_python_types(v) for v in value]
    return value


def _structured_item_to_dict(item: np.void) -> dict[str, Any]:
    """Convert a single structured numpy array item to a dictionary."""
    if not isinstance(item, np.void):
        return _convert_to_python_types(item)

    result = {}
    if item.dtype.names:
        for field_name in item.dtype.names:
            field_value = item[field_name]
            result[field_name] = _convert_structured_value(field_value)
    return result


def _convert_structured_value(value: Any) -> Any:
    """Convert a structured array value to appropriate Python type."""
    if isinstance(value, np.void):
        return _structured_item_to_dict(value)
    elif isinstance(value, np.ndarray):
        if value.size == 0:
            return None
        # Check if this is a structured array first
        elif hasattr(value.dtype, "names") and value.dtype.names:
            # Structured array - convert each element
            return [_structured_item_to_dict(item) for item in value.flat]
        elif value.size == 1:
            return _convert_to_python_types(value.flat[0])
        else:
            return _convert_to_python_types(value)
    else:
        return _convert_to_python_types(value)


def _convert_matlab_datetime(value: Any) -> Any:
    """Convert MATLAB datenum to Python float."""
    if value is None:
        return None
    if isinstance(value, (int, float, np.number)):
        return float(value)
    return value


def _parse_entity_array_scipy(
    entity_arr: np.ndarray, entity_name: str
) -> dict[str, dict[str, Any]]:
    """Parse a scipy entity array directly into BronFormat structure."""
    result = {}

    if entity_arr.size == 0:
        return result

    for entity_idx, entity in enumerate(entity_arr.flat):
        if not isinstance(entity, np.void):
            continue

        # Get BROID from Adm field
        broid = None
        if entity.dtype.names and "Adm" in entity.dtype.names:
            adm = entity["Adm"]
            if adm.size > 0:
                adm_item = adm.flat[0]
                if isinstance(adm_item, np.void) and "BROID" in adm_item.dtype.names:
                    broid_val = adm_item["BROID"]
                    if isinstance(broid_val, np.ndarray) and broid_val.size == 1:
                        broid = str(broid_val.flat[0])
                    else:
                        broid = _convert_to_python_types(broid_val)

        key = str(broid) if broid is not None else f"{entity_name}_{entity_idx}"

        entry_dict = {}
        if entity.dtype.names:
            for field_name in entity.dtype.names:
                field_data = entity[field_name]

                # Special handling for Source with Measurements
                if (
                    field_name == "Source"
                    and isinstance(field_data, np.ndarray)
                    and field_data.size > 0
                ):
                    merged_source = {}

                    for source_item in field_data.flat:
                        if isinstance(source_item, np.void):
                            source_dict = _structured_item_to_dict(source_item)

                            # Process Measurements if present
                            if "Measurements" in source_dict:
                                meas_arr = source_dict["Measurements"]
                                if isinstance(meas_arr, np.ndarray):
                                    # Convert structured array to list of dicts
                                    measurements = []
                                    for meas in meas_arr.flat:
                                        if isinstance(meas, np.void):
                                            meas_dict = _structured_item_to_dict(meas)
                                            for k, v in meas_dict.items():
                                                if (
                                                    "DateTime" in k
                                                    or "Date" in k
                                                    or "Time" in k
                                                ):
                                                    meas_dict[k] = (
                                                        _convert_matlab_datetime(v)
                                                    )
                                                else:
                                                    meas_dict[k] = (
                                                        _convert_to_python_types(v)
                                                    )
                                            measurements.append(meas_dict)
                                        else:
                                            measurements.append(
                                                _convert_to_python_types(meas)
                                            )
                                    source_dict["Measurements"] = measurements
                                elif isinstance(meas_arr, list):
                                    # Already converted to list of dicts by _convert_structured_value
                                    # Just convert datetime fields
                                    for meas_dict in meas_arr:
                                        for k, v in meas_dict.items():
                                            if (
                                                "DateTime" in k
                                                or "Date" in k
                                                or "Time" in k
                                            ):
                                                meas_dict[k] = _convert_matlab_datetime(
                                                    v
                                                )
                                # If it's neither, leave as-is

                            # Merge this source into the result
                            for src_key, src_value in source_dict.items():
                                if src_key not in merged_source:
                                    merged_source[src_key] = src_value
                                elif isinstance(merged_source[src_key], list):
                                    if isinstance(src_value, list):
                                        merged_source[src_key].extend(src_value)
                                    else:
                                        merged_source[src_key].append(src_value)
                                else:
                                    if isinstance(src_value, list):
                                        merged_source[src_key] = [
                                            merged_source[src_key]
                                        ] + src_value
                                    else:
                                        merged_source[src_key] = [
                                            merged_source[src_key],
                                            src_value,
                                        ]

                    entry_dict[field_name] = merged_source

                else:
                    entry_dict[field_name] = _convert_structured_value(field_data)

        result[key] = entry_dict

    return result


def _h5py_group_to_dict(group: h5py.Group, h5file: h5py.File) -> dict[str, Any]:
    """Convert an HDF5 group to a dictionary."""
    result = {}

    for key in group.keys():
        item = group[key]
        if isinstance(item, h5py.Dataset):
            result[key] = _extract_h5py_value(item, h5file)
        elif isinstance(item, h5py.Group):
            if "DateTime" in item and "RawValue" in item:
                measurements = _extract_measurements_from_h5py_group(item, h5file)
                result[key] = measurements
            else:
                result[key] = _h5py_group_to_dict(item, h5file)

    return result


def _extract_measurements_from_h5py_group(
    group: h5py.Group, h5file: h5py.File
) -> list[dict[str, Any]]:
    """Extract measurements from an HDF5 group with DateTime and RawValue."""
    if "DateTime" not in group or "RawValue" not in group:
        return []

    dt_dataset = group["DateTime"]
    rv_dataset = group["RawValue"]

    dt_data = dt_dataset[()]
    rv_data = rv_dataset[()]

    dt_values = []
    if dt_dataset.dtype == object:
        for dt_ref in dt_data.flat:
            if isinstance(dt_ref, h5py.h5r.Reference):
                dt_obj = h5file[dt_ref]
                if isinstance(dt_obj, h5py.Dataset):
                    dt_array = dt_obj[()]
                    dt_values.extend(dt_array.flatten().tolist())
            else:
                dt_values.append(dt_ref)
    else:
        dt_values = dt_data.flatten().tolist()

    rv_values = []
    if rv_dataset.dtype == object:
        for rv_ref in rv_data.flat:
            if isinstance(rv_ref, h5py.h5r.Reference):
                rv_obj = h5file[rv_ref]
                if isinstance(rv_obj, h5py.Dataset):
                    rv_array = rv_obj[()]
                    rv_values.extend(rv_array.flatten().tolist())
            else:
                rv_values.append(rv_ref)
    else:
        rv_values = rv_data.flatten().tolist()

    min_length = min(len(dt_values), len(rv_values))
    measurements = []
    for i in range(min_length):
        meas_dict = {
            "DateTime": _convert_matlab_datetime(dt_values[i]),
            "RawValue": _convert_to_python_types(rv_values[i]),
        }

        for key in group.keys():
            if key not in ["DateTime", "RawValue"]:
                sub_dataset = group[key]
                _ = sub_dataset[()]
                value = _extract_h5py_value(sub_dataset, h5file)
                meas_dict[key] = _convert_to_python_types(value)

        measurements.append(meas_dict)

    return measurements


def _extract_measurements_from_h5py_dataset(
    dataset: h5py.Dataset | h5py.Group, h5file: h5py.File
) -> list[dict[str, Any]]:
    """Extract measurements from an HDF5 Measurements dataset with references."""
    measurements = []

    if isinstance(dataset, h5py.Group):
        return _extract_measurements_from_h5py_group(dataset, h5file)
    elif isinstance(dataset, h5py.Dataset):
        data = dataset[()]
        if data.size == 0:
            return []

        # Collect all DateTime and RawValue references
        all_dt_refs = []
        all_rv_refs = []

        for ref in data.flat:
            if isinstance(ref, h5py.h5r.Reference):
                ref_obj = h5file[ref]
                if isinstance(ref_obj, h5py.Group):
                    if "DateTime" in ref_obj:
                        dt_data = ref_obj["DateTime"][()]
                        all_dt_refs.extend(dt_data.flat)
                    if "RawValue" in ref_obj:
                        rv_data = ref_obj["RawValue"][()]
                        all_rv_refs.extend(rv_data.flat)

        # Extract all DateTime values
        dt_values = []
        for dt_ref in all_dt_refs:
            if isinstance(dt_ref, h5py.h5r.Reference):
                dt_obj = h5file[dt_ref]
                if isinstance(dt_obj, h5py.Dataset):
                    dt_array = dt_obj[()]
                    dt_values.extend(dt_array.flatten().tolist())
            elif isinstance(dt_ref, (int, float, np.number)):
                dt_values.append(dt_ref)

        # Extract all RawValue values
        rv_values = []
        for rv_ref in all_rv_refs:
            if isinstance(rv_ref, h5py.h5r.Reference):
                rv_obj = h5file[rv_ref]
                if isinstance(rv_obj, h5py.Dataset):
                    rv_array = rv_obj[()]
                    rv_values.extend(rv_array.flatten().tolist())
            elif isinstance(rv_ref, (int, float, np.number)):
                rv_values.append(rv_ref)

        if len(dt_values) == 0 or len(rv_values) == 0:
            return []

        min_length = min(len(dt_values), len(rv_values))
        for i in range(min_length):
            measurements.append(
                {
                    "DateTime": _convert_matlab_datetime(dt_values[i]),
                    "RawValue": _convert_to_python_types(rv_values[i]),
                }
            )

    return measurements


def _extract_h5py_value(dataset: h5py.Dataset, h5file: h5py.File) -> Any:
    """Extract a value from an HDF5 dataset."""
    data = dataset[()]

    if dataset.dtype == np.uint16:
        chars = data.flatten().tolist()
        chars = [chr(c) for c in chars if c > 0]
        return "".join(chars) if chars else None

    if dataset.dtype == object and data.size > 0:
        # Check if this is a Measurements dataset by looking at the first reference
        first = data.flat[0]
        measurements_dataset = False
        if isinstance(first, h5py.h5r.Reference):
            ref_obj = h5file[first]
            if isinstance(ref_obj, h5py.Group):
                if "DateTime" in ref_obj and "RawValue" in ref_obj:
                    measurements_dataset = True

        if measurements_dataset:
            return _extract_measurements_from_h5py_dataset(dataset, h5file)

        # Handle single reference
        if isinstance(first, h5py.h5r.Reference):
            ref_obj = h5file[first]
            if isinstance(ref_obj, h5py.Group):
                return _h5py_group_to_dict(ref_obj, h5file)
            elif isinstance(ref_obj, h5py.Dataset):
                return _extract_h5py_value(ref_obj, h5file)

        if data.size > 1:
            items = []
            for ref in data.flat:
                if isinstance(ref, h5py.h5r.Reference):
                    ref_obj = h5file[ref]
                    if isinstance(ref_obj, h5py.Group):
                        if "DateTime" in ref_obj and "RawValue" in ref_obj:
                            items.extend(
                                _extract_measurements_from_h5py_dataset(ref_obj, h5file)
                            )
                        else:
                            items.append(_h5py_group_to_dict(ref_obj, h5file))
                    elif isinstance(ref_obj, h5py.Dataset):
                        items.append(_extract_h5py_value(ref_obj, h5file))
                    else:
                        items.append(_convert_to_python_types(ref))
                else:
                    items.append(_convert_to_python_types(ref))
            return items

    if data.size == 1:
        value = data.item()
        if isinstance(value, np.generic):
            return value.item()
        return value

    if data.size == 0:
        return None

    if np.issubdtype(dataset.dtype, np.number):
        return data.flatten().tolist()

    return _convert_to_python_types(data)


def _parse_h5py_entity_to_dict(
    entity_obj: h5py.Dataset | h5py.Group, entity_name: str, h5file: h5py.File
) -> dict[str, Any]:
    """Parse an HDF5 entity object to a dictionary."""
    if isinstance(entity_obj, h5py.Dataset):
        data = entity_obj[()]
        if entity_obj.dtype == object and data.size > 0:
            result = {}
            for i, ref in enumerate(data.flat):
                if isinstance(ref, h5py.h5r.Reference):
                    deref_obj = h5file[ref]
                    if isinstance(deref_obj, h5py.Group):
                        sub_dict = _h5py_group_to_dict(deref_obj, h5file)
                        key = str(i)
                        if "Adm" in sub_dict and isinstance(sub_dict["Adm"], dict):
                            if "BROID" in sub_dict["Adm"]:
                                key = str(sub_dict["Adm"]["BROID"])
                            elif f"{entity_name}ID" in sub_dict["Adm"]:
                                key = str(sub_dict["Adm"][f"{entity_name}ID"])
                        result[key] = sub_dict
            return result

    elif isinstance(entity_obj, h5py.Group):
        has_ref_datasets = any(
            isinstance(entity_obj[k], h5py.Dataset) and entity_obj[k].dtype == object
            for k in entity_obj.keys()
        )

        if has_ref_datasets:
            first_dataset = None
            for key in entity_obj.keys():
                if (
                    isinstance(entity_obj[key], h5py.Dataset)
                    and entity_obj[key].dtype == object
                ):
                    first_dataset = entity_obj[key]
                    break

            if first_dataset is not None:
                if len(first_dataset.shape) == 2:
                    n_entities = first_dataset.shape[1]
                else:
                    n_entities = first_dataset.shape[0]

                result = {}
                for i in range(n_entities):
                    entry_dict = {}
                    broid = None

                    for sub_name in entity_obj.keys():
                        sub_obj = entity_obj[sub_name]

                        if isinstance(sub_obj, h5py.Dataset):
                            if sub_obj.dtype == object:
                                sub_data = sub_obj[()]
                                if len(sub_obj.shape) == 2:
                                    ref = (
                                        sub_data[0, i]
                                        if len(sub_data.shape) >= 2
                                        else sub_data.flat[i]
                                    )
                                else:
                                    ref = sub_data[i] if i < len(sub_data) else None

                                if isinstance(ref, h5py.h5r.Reference):
                                    deref_obj = h5file[ref]
                                    if isinstance(deref_obj, h5py.Group):
                                        sub_dict = _h5py_group_to_dict(
                                            deref_obj, h5file
                                        )

                                        if sub_name == "Adm":
                                            if "BROID" in sub_dict:
                                                broid = sub_dict["BROID"]
                                        elif (
                                            sub_name == "Source"
                                            and "Source" in entry_dict
                                        ):
                                            existing_source = entry_dict["Source"]
                                            for key, val in sub_dict.items():
                                                if key not in existing_source:
                                                    existing_source[key] = val
                                                elif isinstance(
                                                    existing_source[key], list
                                                ):
                                                    existing_source[key].extend(
                                                        val
                                                        if isinstance(val, list)
                                                        else [val]
                                                    )
                                                else:
                                                    existing_source[key] = [
                                                        existing_source[key],
                                                        val,
                                                    ]
                                        else:
                                            entry_dict[sub_name] = sub_dict
                            else:
                                entry_dict[sub_name] = _extract_h5py_value(
                                    sub_obj, h5file
                                )

                    key = str(broid) if broid is not None else f"{entity_name}_{i}"
                    result[key] = entry_dict

                return result
        else:
            # Entity is a group with sub-groups
            entry_dict = _h5py_group_to_dict(entity_obj, h5file)

            key = f"{entity_name}_0"
            if "Adm" in entry_dict and isinstance(entry_dict["Adm"], dict):
                if "BROID" in entry_dict["Adm"]:
                    broid = entry_dict["Adm"]["BROID"]
                    if broid is not None:
                        key = str(broid)
                elif f"{entity_name}ID" in entry_dict["Adm"]:
                    entity_id = entry_dict["Adm"][f"{entity_name}ID"]
                    if entity_id is not None:
                        key = str(entity_id)

            return {key: entry_dict}

    return {}


def _parse_scipy_data_to_bronformat(data: dict[str, Any]) -> BronFormat:
    """Parse scipy-loaded data dictionary to BronFormat."""
    result = BronFormat()

    for entity_name in ENTITY_TYPES:
        if entity_name in data:
            entity_arr = data[entity_name]
            if isinstance(entity_arr, np.ndarray) and entity_arr.size > 0:
                entity_dict = _parse_entity_array_scipy(entity_arr, entity_name)
                if entity_dict:
                    setattr(result, entity_name, entity_dict)

    return result


def _parse_h5py_data_to_bronformat(h5file: h5py.File) -> BronFormat:
    """Parse h5py File object to BronFormat."""
    result = BronFormat()

    for entity_name in ENTITY_TYPES:
        if entity_name in h5file:
            entity_obj = h5file[entity_name]
            entity_dict = _parse_h5py_entity_to_dict(entity_obj, entity_name, h5file)
            if entity_dict:
                setattr(result, entity_name, entity_dict)

    return result


def read_bronformat_scipy(filepath: str | Path) -> BronFormat:
    """Read a Bronformat file (< v7.3) using SciPy and return BronFormat directly."""
    filepath = Path(filepath)
    logger.info(f"Loading Bronformat file (scipy backend): {filepath}")

    try:
        data = scipy.io.loadmat(filepath)
    except NotImplementedError as e:
        logger.error("HDF5 file detected - scipy backend cannot handle v7.3+ files")
        raise BronformatParseError(
            "Detected a v7.3+ (HDF5) file. Use the h5py backend for HDF5 files."
        ) from e

    return _parse_scipy_data_to_bronformat(data)


def read_bronformat_h5py(filepath: str | Path) -> BronFormat:
    """Read a Bronformat file (v7.3+) using h5py and return BronFormat directly."""
    filepath = Path(filepath)
    logger.info(f"Loading Bronformat file (h5py backend): {filepath}")

    try:
        with h5py.File(filepath, "r") as h5file:
            return _parse_h5py_data_to_bronformat(h5file)
    except Exception as e:
        logger.error(f"Error reading HDF5 file: {e}")
        raise BronformatParseError(
            f"Failed to read HDF5 file with h5py backend: {e}"
        ) from e


def read_bronformat(filepath: str | Path, backend: str = "auto") -> BronFormat:
    """Read a Bronformat file and return BronFormat structure.

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
        Each entity contains nested dictionaries mirroring the file structure.

    Raises
    ------
    ValueError
        If file extension is not supported or backend is invalid.
    BronformatParseError
        If file cannot be parsed.
    """
    filepath = Path(filepath)

    if filepath.suffix.lower() in (".hdf5", ".bronx"):
        backend = "h5py"
    elif filepath.suffix.lower() == ".bron2":
        backend = "scipy"
    elif filepath.suffix.lower() == ".bron":
        raise BronformatParseError(
            "The .bron extension is not supported. Please convert your file."
        )

    if backend == "scipy":
        return read_bronformat_scipy(filepath)
    elif backend == "h5py":
        return read_bronformat_h5py(filepath)
    elif backend == "auto":
        if filepath.suffix.lower() in (".hdf5", ".bronx"):
            return read_bronformat_h5py(filepath)
        elif filepath.suffix.lower() == ".bron2":
            return read_bronformat_scipy(filepath)
        else:
            try:
                return read_bronformat_scipy(filepath)
            except Exception:
                return read_bronformat_h5py(filepath)
    else:
        raise ValueError(
            "Invalid backend. Choose 'auto', 'scipy' (for .bron2), or 'h5py' (for .hdf5/.bronx)."
        )
