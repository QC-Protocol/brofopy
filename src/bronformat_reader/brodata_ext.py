"""brodata integration for bronformat_reader."""

from __future__ import annotations

import pandas as pd
import brodata  # noqa: F401  – imported so the brodata dependency is exercised


def from_brodata() -> pd.DataFrame:
    """Fetch Bronformat data via the brodata package and return it as a DataFrame.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing data retrieved through brodata.

    Raises
    ------
    NotImplementedError
        Until the retrieval implementation is complete.

    Examples
    --------
    >>> df = from_brodata()
    >>> isinstance(df, pd.DataFrame)
    True
    """
    raise NotImplementedError("from_brodata is not yet implemented.")
