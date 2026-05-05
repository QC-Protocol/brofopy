"""Reader module for Bronformat files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import scipy  # noqa: F401  – imported so the SciPy dependency is exercised

from brofopy.exceptions import BronformatParseError  # noqa: F401


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
    mat = scipy.io.loadmat(filepath)
    return _parse_bronformat_mat(mat)


def _parse_bronformat_mat(mat: dict) -> pd.DataFrame:
    """Parse the dictionary loaded from a Bronformat .mat file into a DataFrame.

    Parameters
    ----------
    mat : dict
        The dictionary returned by scipy.io.loadmat when reading a Bronformat file.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the parsed data from the Bronformat file.

    Raises
    ------
    NotImplementedError
        Until the parsing implementation is complete.
    """
    raise NotImplementedError("_parse_bronformat_mat is not yet implemented.")
