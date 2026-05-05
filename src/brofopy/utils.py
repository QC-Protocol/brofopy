"""Utility helpers for brofopy."""

from __future__ import annotations

import pandas as pd


def validate_data(df: pd.DataFrame) -> None:
    """Validate that *df* meets the expected Bronformat schema.

    This is a placeholder demonstrating where helper / validation functions
    live.  Extend this function (or add new ones) to enforce column names,
    dtypes, and value ranges before further processing.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to validate.

    Raises
    ------
    ValueError
        If *df* does not satisfy the expected schema.
    NotImplementedError
        Until the validation logic is implemented.
    """
    raise NotImplementedError("validate_data is not yet implemented.")
