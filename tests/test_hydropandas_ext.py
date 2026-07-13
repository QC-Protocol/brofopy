"""Tests for brofopy HydroPandas extension."""

from pathlib import Path

from brofopy import BronFormat, read_bronformat


data_path = Path(__file__).parent / "data"


def test_to_obscollection_with_gld() -> None:
    """Test to_obscollection with GLD data from HDF5 file."""
    bf = read_bronformat(data_path / "gld_bhr.hdf5")
    oc = bf.to_obscollection(entity="GLD", name="GLDCollection")
    assert oc.name == "GLDCollection"


def test_to_obscollection_from_file() -> None:
    """Test to_obscollection using from_file method."""
    bf = BronFormat.from_file(data_path / "gld_bhr.hdf5")
    oc = bf.to_obscollection(entity="GLD", name="FromFileCollection")
    assert oc.name == "FromFileCollection"


def test_to_obscollection_empty() -> None:
    """Test to_obscollection with empty BronFormat."""
    bf = BronFormat()
    oc = bf.to_obscollection(entity="GLD", name="EmptyCollection")
    assert oc.name == "EmptyCollection"
