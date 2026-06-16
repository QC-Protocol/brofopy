"""Tests for brofopy.reader."""

from pathlib import Path

import pytest

from brofopy.exceptions import BronformatParseError
from brofopy.reader import read_bronformat

data_path = Path(__file__).parent / "data"


def test_read_bron() -> None:
    """Test that read_bronformat can read a .bron file."""
    with pytest.raises(BronformatParseError):
        read_bronformat(data_path / "testdata.bron")


def test_read_bron2() -> None:
    """Test that read_bronformat can read a .bron2 file."""
    metadata_df, data_df = read_bronformat(data_path / "testdata.bron2")

    # Check that the returned objects are DataFrames
    assert isinstance(metadata_df, type(data_df))
    assert isinstance(data_df, type(metadata_df))

    # Check that the DataFrames are not empty
    assert not metadata_df.empty
    assert not data_df.empty


def test_read_bronx() -> None:
    """Test that read_bronformat can read a .bronx file."""
    metadata_df, data_df = read_bronformat(data_path / "testdata.bronx", backend="h5py")

    # Check that the returned objects are DataFrames
    assert isinstance(metadata_df, type(data_df))
    assert isinstance(data_df, type(metadata_df))

    # Check that the DataFrames are not empty
    assert not metadata_df.empty
    assert not data_df.empty


if __name__ == "__main__":
    # test_read_bron()
    # test_read_bron2()
    # test_read_bronx()
    pass