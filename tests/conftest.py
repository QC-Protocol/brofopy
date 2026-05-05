"""Shared pytest fixtures for bronformat_reader tests."""

import pandas as pd
import pytest


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Return a simple dummy DataFrame for use in tests.

    Returns
    -------
    pd.DataFrame
        A small DataFrame with two columns: ``value`` (float) and
        ``label`` (str).
    """
    return pd.DataFrame(
        {
            "value": [1.0, 2.0, 3.0],
            "label": ["a", "b", "c"],
        }
    )
