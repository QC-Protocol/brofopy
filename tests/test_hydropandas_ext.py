"""Tests for bronformat_reader.hydropandas_ext."""

import pytest

from bronformat_reader.hydropandas_ext import to_obscollection


def test_to_obscollection_raises_not_implemented(sample_dataframe) -> None:
    """to_obscollection should raise NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        to_obscollection(sample_dataframe, meta={})
