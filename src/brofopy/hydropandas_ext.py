"""HydroPandas integration for brofopy."""

from __future__ import annotations

import pandas as pd
import hydropandas as hpd
from hydropandas import ObsCollection


def to_obscollection(df: pd.DataFrame, meta: dict) -> ObsCollection:
    """Convert a DataFrame to a HydroPandas ObsCollection.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame produced by :func:`brofopy.reader.read_bronformat`.
    meta : dict
        Metadata dictionary with observation attributes (e.g. location,
        unit, source).

    Returns
    -------
    ObsCollection
        A HydroPandas ``ObsCollection`` built from *df* and *meta*.

    Raises
    ------
    NotImplementedError
        Until the conversion implementation is complete.

    Examples
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame()
    >>> oc = to_obscollection(df, meta={})
    """
    raise NotImplementedError("to_obscollection is not yet implemented.")
