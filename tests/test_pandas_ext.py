"""Tests for brofopy pandas extension (ext.pd module)."""

from pathlib import Path

import pandas as pd

from brofopy import BronFormat, read_bronformat
from brofopy.ext.pd import matlab_datetime_to_pandas_timestamp, to_dataframe

data_path = Path(__file__).parent / "data"


class TestMatlabDatetimeToPandasTimestamp:
    """Tests for matlab_datetime_to_pandas_timestamp function."""

    def test_matlab_datetime_zero(self):
        """Test conversion of MATLAB datetime 0 (Jan 1, 0000)."""
        result = matlab_datetime_to_pandas_timestamp(0)
        # MATLAB datenum 0 is 0000-01-00, offset by 719529 days from 1970-01-01
        expected = pd.Timestamp("1970-01-01") + pd.to_timedelta(-719529, unit="D")
        assert result == expected

    def test_matlab_datetime_epoch(self):
        """Test conversion of MATLAB datetime for Unix epoch (Jan 1, 1970)."""
        # MATLAB datenum for 1970-01-01 is 719529
        result = matlab_datetime_to_pandas_timestamp(719529)
        expected = pd.Timestamp("1970-01-01")
        assert result == expected

    def test_matlab_datetime_recent(self):
        """Test conversion of a recent MATLAB datetime."""
        # MATLAB datenum for 2023-01-01 is 738887
        result = matlab_datetime_to_pandas_timestamp(738887)
        expected = pd.Timestamp("2023-01-01")
        assert result == expected

    def test_matlab_datetime_with_fraction(self):
        """Test conversion of MATLAB datetime with fractional day."""
        # 738887.5 is 2023-01-01 12:00:00
        result = matlab_datetime_to_pandas_timestamp(738887.5)
        expected = pd.Timestamp("2023-01-01 12:00:00")
        assert result == expected

    def test_matlab_datetime_before_epoch(self):
        """Test conversion of MATLAB datetime before Unix epoch."""
        # MATLAB datenum for 1960-01-01 is 715876
        result = matlab_datetime_to_pandas_timestamp(715876)
        expected = pd.Timestamp("1960-01-01")
        assert result == expected


class TestToDataframe:
    """Tests for to_dataframe function."""

    def test_to_dataframe_empty_bronformat(self):
        """Test to_dataframe with empty BronFormat."""
        bf = BronFormat()
        result = to_dataframe(bf)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        # Should have expected columns in MultiIndex
        assert "Entity" in result.index.names
        assert "BROID" in result.index.names

    def test_to_dataframe_single_gld_entry(self):
        """Test to_dataframe with single GLD entry containing measurements."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Adm": {"BROID": "gld1", "name": "Test Level"},
                    "Source": {
                        "Measurements": [
                            {"DateTime": 738887.0, "RawValue": 10.5},
                            {"DateTime": 738888.0, "RawValue": 11.2},
                        ]
                    },
                }
            }
        )
        result = to_dataframe(bf)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2  # Two measurements
        assert isinstance(result.index, pd.MultiIndex)
        assert result.index.names == ["Entity", "BROID"]

    def test_to_dataframe_multiple_entities(self):
        """Test to_dataframe with multiple entity types."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Source": {
                        "Measurements": [
                            {"DateTime": 738887.0, "RawValue": 10.5},
                        ]
                    },
                }
            },
            GMW={
                "gmw1": {
                    "Source": {
                        "Measurements": [
                            {"DateTime": 738887.5, "RawValue": 20.0},
                        ]
                    },
                }
            },
        )
        result = to_dataframe(bf)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2  # One from each entity
        # Check both entities are in the index
        entities = result.index.get_level_values("Entity").unique()
        assert "GLD" in entities
        assert "GMW" in entities

    def test_to_dataframe_no_measurements(self):
        """Test to_dataframe when entities have no measurements."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Adm": {"BROID": "gld1", "name": "Test"},
                    "Source": {},  # No Measurements
                }
            }
        )
        result = to_dataframe(bf)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0  # No measurements to convert

    def test_to_dataframe_datetime_conversion(self):
        """Test that MATLAB datetimes are converted to pandas Timestamps."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Source": {
                        "Measurements": [
                            {"DateTime": 738887.5, "RawValue": 10.5},
                        ]
                    },
                }
            }
        )
        result = to_dataframe(bf)
        assert "DateTime" in result.columns
        # Check that DateTime column contains pd.Timestamp
        datetime_value = result["DateTime"].iloc[0]
        assert isinstance(datetime_value, pd.Timestamp)
        # 738887.5 is 2023-01-01 12:00:00
        expected = pd.Timestamp("2023-01-01 12:00:00")
        assert datetime_value == expected

    def test_to_dataframe_from_real_file(self):
        """Test to_dataframe with real HDF5 file."""
        bf = read_bronformat(data_path / "gld_bhr.hdf5")
        result = to_dataframe(bf)
        assert isinstance(result, pd.DataFrame)
        # Should have at least some measurements from GLD
        if bf.GLD is not None:
            total_measurements = sum(
                len(entry.get("Source", {}).get("Measurements", []))
                for entry in bf.GLD.values()
            )
            if total_measurements > 0:
                assert len(result) >= total_measurements

    def test_to_dataframe_preserves_all_fields(self):
        """Test that to_dataframe preserves all measurement fields."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Source": {
                        "Measurements": [
                            {
                                "DateTime": 738827.0,
                                "RawValue": 10.5,
                                "CorrectedValue": 10.6,
                                "QualityCode": 1,
                            },
                        ]
                    },
                }
            }
        )
        result = to_dataframe(bf)
        assert "DateTime" in result.columns
        assert "RawValue" in result.columns
        assert "CorrectedValue" in result.columns
        assert "QualityCode" in result.columns

    def test_to_dataframe_null_datetime(self):
        """Test to_dataframe handles None/NaN datetime values."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Source": {
                        "Measurements": [
                            {"DateTime": None, "RawValue": 10.5},
                        ]
                    },
                }
            }
        )
        result = to_dataframe(bf)
        assert len(result) == 1
        # None datetime should be preserved as None or converted to NaT
        assert pd.isna(result["DateTime"].iloc[0])

    def test_to_dataframe_all_entity_types(self):
        """Test to_dataframe with all supported entity types."""
        entity_types = ["GMN", "GMW", "GLD", "GAR", "BHR", "GUF", "GPD"]
        bf_data = {}
        for entity in entity_types:
            bf_data[entity] = {
                "test_id": {
                    "Source": {
                        "Measurements": [
                            {"DateTime": 738887.0, "RawValue": 1.0},
                        ]
                    },
                }
            }
        bf = BronFormat(**bf_data)
        result = to_dataframe(bf)
        assert isinstance(result, pd.DataFrame)
        # Should have one row per entity
        assert len(result) == len(entity_types)
        # Check all entities are represented
        entities = result.index.get_level_values("Entity").unique()
        for entity in entity_types:
            assert entity in entities

    def test_to_dataframe_method_on_bronformat(self):
        """Test that to_dataframe can be called as a method on BronFormat."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Source": {
                        "Measurements": [
                            {"DateTime": 738827.0, "RawValue": 10.5},
                        ]
                    },
                }
            }
        )
        # Call as method
        result = bf.to_dataframe()
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
