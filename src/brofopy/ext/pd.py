"""Pandas extension for brofopy.

This module provides functions to convert BronFormat data to pandas DataFrames.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from brofopy.bronformat import BronFormat


def matlab_datetime_to_pandas_timestamp(matlab_datetime: float) -> pd.Timestamp:
    """Convert MATLAB datetime to pandas Timestamp.

    Parameters
    ----------
    matlab_datetime : float
        MATLAB datetime value.

    Returns
    -------
    pd.Timestamp
        Corresponding pandas Timestamp.
    """
    # MATLAB datenum is days since 0000-01-00, while pandas Timestamp is based on 1970-01-01.
    # The offset between the two is 719529 days.
    offset_days = 719529
    timestamp = pd.Timestamp("1970-01-01") + pd.to_timedelta(
        matlab_datetime - offset_days, unit="D"
    )
    return timestamp


def to_dataframe(bronformat: "BronFormat") -> pd.DataFrame:
    """Convert BronFormat data to a pandas DataFrame.

    This flattens the nested BronFormat structure into a DataFrame with
    time series measurements. MATLAB datetimes are converted to pandas Timestamps.

    Parameters
    ----------
    bronformat : BronFormat
        A BronFormat object with entity data.

    Returns
    -------
    pd.DataFrame
        DataFrame with MultiIndex (Entity, BROID) and columns for DateTime,
        RawValue, and other measurement fields.
    """
    data_rows = []

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

    for entity_name in entity_types:
        entity_data = getattr(bronformat, entity_name, None)
        if entity_data is None:
            continue

        for entity_id, entry in entity_data.items():
            # Process Source/Measurements for time series
            if "Source" in entry and isinstance(entry["Source"], dict):
                source = entry["Source"]
                measurements = source.get("Measurements", [])

                if isinstance(measurements, list):
                    for measurement in measurements:
                        if not isinstance(measurement, dict):
                            continue

                        row = {
                            "Entity": entity_name,
                            "BROID": entity_id,
                        }

                        for key, value in measurement.items():
                            # Convert MATLAB datetime to pandas Timestamp
                            if "DateTime" in key or "Date" in key:
                                if value is not None:
                                    try:
                                        row[key] = matlab_datetime_to_pandas_timestamp(
                                            float(value)
                                        )
                                    except (ValueError, TypeError, OverflowError):
                                        # Fallback: keep as numeric if conversion fails
                                        row[key] = float(value)
                                else:
                                    row[key] = value
                            else:
                                row[key] = value

                        data_rows.append(row)

    if not data_rows:
        # Return empty DataFrame with expected columns
        return pd.DataFrame(
            columns=["Entity", "BROID", "DateTime", "RawValue"]
        ).set_index(["Entity", "BROID"])

    df = pd.DataFrame(data_rows)

    # Set MultiIndex
    if "Entity" in df.columns and "BROID" in df.columns:
        df = df.set_index(["Entity", "BROID"])

    return df
