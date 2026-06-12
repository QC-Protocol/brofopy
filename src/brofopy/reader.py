"""Reader module for Bronformat files."""

from pathlib import Path
from typing import Any, Literal

import h5py as h5py
import pandas as pd
import scipy as scipy

from brofopy.exceptions import BronformatParseError


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

    if extension == ".bron":
        raise BronformatParseError(
            "The .bron extension is not supported. Please convert your file to .bron2 format. "
            "The .bron extension could maybe be supported in the future. But it would require"
            " more work investigating scipy.io.matlab MatlabOpaque and MatlabObject types."
        )
    assert extension == extension_accepted, (
        f"File must have {extension_accepted} extension, got {extension}"
    )

    return


def read_bronformat(
    filepath: str | Path, backend: Literal["scipy", "h5py"] = "scipy"
) -> pd.DataFrame:
    """Read a Bronformat file and return its contents as a DataFrame.

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
    pd.DataFrame
        A DataFrame containing the data from the Bronformat file.

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


def read_bronformat_scipy(filepath: str | Path) -> pd.DataFrame:
    """Read a Bronformat file (< v7.3) using SciPy and return a DataFrame.

    SciPy natively supports reading MATLAB files up to version 7.2. If the
    Bronformat file was saved as v7.3 or higher (HDF5), SciPy will raise a
    NotImplementedError.

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
        If the file cannot be parsed as a valid Bronformat or if it's an HDF5 file.

    Examples
    --------
    >>> df = read_bronformat("sample.bron2", backend="scipy")
    >>> isinstance(df, pd.DataFrame)
    True
    """
    _check_extension(filepath)

    try:
        io = scipy.io.loadmat(filepath)
    except NotImplementedError as e:
        raise BronformatParseError(
            "Detected a v7.3+ (HDF5) file. The 'scipy' backend only supports "
            "MATLAB files < v7.3. Please use the 'h5py' backend (when implemented) "
            "or re-save your file in an older format."
        ) from e

    return parse_bronformat_scipy(io)


def parse_bronformat_scipy(d: dict[str, Any]) -> pd.DataFrame:
    """Parse the dictionary loaded from a < v7.3 Bronformat file into a DataFrame.

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
    pd.DataFrame
        A DataFrame containing the parsed data from the Bronformat file.
    """
    # raise BronformatParseError(
    #     "Parsing of Bronformat .mat files is not yet implemented."
    # )
    return d


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
    from pathlib import Path

    path = Path.cwd().parent.parent / "tests/data/testdata.bron2"
    file = read_bronformat(path, backend="scipy")
    print(file)
