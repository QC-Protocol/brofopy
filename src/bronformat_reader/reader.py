"""Reader module for Bronformat files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import scipy  # noqa: F401  – imported so the SciPy dependency is exercised

from bronformat_reader.exceptions import BronformatParseError  # noqa: F401


def read_bronformat(filepath: str | Path) -> pd.DataFrame:
    """Read a Bronformat file and return its contents as a DataFrame.

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
        If the file cannot be parsed as a valid Bronformat.
    NotImplementedError
        Until the reader implementation is complete.

    Examples
    --------
    >>> df = read_bronformat("sample.bro")
    >>> isinstance(df, pd.DataFrame)
    True
    """
    raise NotImplementedError("read_bronformat is not yet implemented.")
