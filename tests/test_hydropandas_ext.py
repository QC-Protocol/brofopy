"""Tests for brofopy.hydropandas_ext."""

from pathlib import Path

from hydropandas import ObsCollection

from brofopy import read_bronformat
from brofopy.ext.hpd import to_obscollection

data_path = Path(__file__).parent / "data"


def test_to_obscollection() -> None:
    """Test that to_obscollection can convert a DataFrame to an ObsCollection."""
    metadata_df, data_df = read_bronformat(data_path / "testdata.bron2")
    oc = to_obscollection(data_df, metadata_df, entity="GLD", name="TestObsCollection")
    assert oc.name == "TestObsCollection"
    assert isinstance(oc, ObsCollection)
