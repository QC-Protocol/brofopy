"""Tests for brofopy.hydropandas_ext."""

import pytest
import scipy as scipy

from brofopy.ext.hpd import to_obscollection


def test_to_obscollection_raises_not_implemented(sample_dataframe) -> None:
    """to_obscollection should raise NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        to_obscollection(sample_dataframe, meta={})


if __name__ == "__main__":
    from pathlib import Path

    from brofopy.reader import read_bronformat

    data_path = Path.cwd() / "data/testdata.bron2"
    metadata_df, data_df = read_bronformat(data_path)
    oc = to_obscollection(data_df, metadata_df, entity="GLD", name="Test ObsCollection")

