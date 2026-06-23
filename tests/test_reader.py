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


def test_read_gar_hdf5() -> None:
    """Test that read_bronformat can read a GAR-only .hdf5 file."""
    metadata_df, data_df = read_bronformat(data_path / "gar.hdf5", backend="h5py")

    # Check that the returned objects are DataFrames
    assert isinstance(metadata_df, type(data_df))
    assert isinstance(data_df, type(metadata_df))

    # Check that the DataFrames are not empty
    assert not metadata_df.empty
    # GAR may or may not have data rows depending on the file

    # Check that GAR entity is present
    assert "GAR" in metadata_df.index.get_level_values(0).unique()


def test_read_gld_hdf5() -> None:
    """Test that read_bronformat can read a GLD-only .hdf5 file."""
    # Use gld_bhr.hdf5 which has GLD data
    metadata_df, data_df = read_bronformat(data_path / "gld_bhr.hdf5", backend="h5py")

    # Check that the returned objects are DataFrames
    assert isinstance(metadata_df, type(data_df))
    assert isinstance(data_df, type(metadata_df))

    # Check that the DataFrames are not empty
    assert not metadata_df.empty
    assert not data_df.empty

    # Check that GLD entity is present
    assert "GLD" in metadata_df.index.get_level_values(0).unique()


def test_read_bhr_hdf5() -> None:
    """Test that read_bronformat can read a BHR-only .hdf5 file."""
    metadata_df, data_df = read_bronformat(data_path / "gld_bhr.hdf5", backend="h5py")

    # Check that the returned objects are DataFrames
    assert isinstance(metadata_df, type(data_df))
    assert isinstance(data_df, type(metadata_df))

    # Check that the DataFrames are not empty
    assert not metadata_df.empty

    # Check that BHR entity is present
    assert "BHR" in metadata_df.index.get_level_values(0).unique()


def test_read_guf_hdf5() -> None:
    """Test that read_bronformat can read a GUF-only .hdf5 file."""
    metadata_df, data_df = read_bronformat(data_path / "guf_gpd.hdf5", backend="h5py")

    # Check that the returned objects are DataFrames
    assert isinstance(metadata_df, type(data_df))
    assert isinstance(data_df, type(metadata_df))

    # Check that the DataFrames are not empty
    assert not metadata_df.empty

    # Check that GUF entity is present
    assert "GUF" in metadata_df.index.get_level_values(0).unique()


def test_read_gpd_hdf5() -> None:
    """Test that read_bronformat can read a GPD-only .hdf5 file."""
    metadata_df, data_df = read_bronformat(data_path / "guf_gpd.hdf5", backend="h5py")

    # Check that the returned objects are DataFrames
    assert isinstance(metadata_df, type(data_df))
    assert isinstance(data_df, type(metadata_df))

    # Check that the DataFrames are not empty
    assert not metadata_df.empty

    # Check that GPD entity is present in metadata
    assert "GPD" in metadata_df.index.get_level_values(0).unique()
    
    # Check that GPD Volumes data is in data_df instead of metadata_df
    assert "GPD" in data_df.index.get_level_values(0).unique()
    
    # Check that Volumes subentity is not in metadata_df (it should be in data_df now)
    gpd_metadata = metadata_df.loc["GPD"]
    assert "Volumes" not in gpd_metadata.index.get_level_values("SubEntity").unique()
    
    # Check that data_df contains the expected columns for GPD Volumes
    expected_columns = ["BeginDate", "EndDate", "GPDID", "Volume", "WaterInOut"]
    for col in expected_columns:
        assert col in data_df.columns, f"Expected column {col} not found in data_df"
    
    # Check that GPD Volumes data is not empty
    gpd_data = data_df.loc["GPD"]
    assert not gpd_data.empty
    assert len(gpd_data) > 0
