"""Comprehensive tests for brofopy.bronformat module.

Tests all methods and functions in the bronformat module:
- BronFormat class methods (__repr__, to_dict, print)
- Helper functions (_get_entity_id_from_row, _convert_from_dataframes)
- Main function (read_bronformat - basic coverage, more in test_reader.py)
"""

from pathlib import Path

import pandas as pd

from brofopy.bronformat import (
    BronFormat,
    _convert_from_dataframes,
    _get_entity_id_from_row,
    read_bronformat,
)


class TestBronFormatClass:
    """Tests for the BronFormat dataclass."""

    def test_empty_bronformat_creation(self):
        """Test creating an empty BronFormat object."""
        bf = BronFormat()
        assert bf.GMN is None
        assert bf.GMW is None
        assert bf.GLD is None
        assert bf.GAR is None
        assert bf.BHR is None
        assert bf.GUF is None
        assert bf.GPD is None
        assert bf.Proces is None
        assert bf.IN is None
        assert bf.QC is None
        assert bf.File is None
        assert bf.GIS is None
        assert bf.Cache is None
        assert bf.SAD is None

    def test_bronformat_with_data(self):
        """Test creating a BronFormat object with data."""
        bf = BronFormat(GMN={"test_id": {"Adm": {"name": "test"}}})
        assert bf.GMN is not None
        assert bf.GMN == {"test_id": {"Adm": {"name": "test"}}}
        assert bf.GMW is None

    def test_bronformat_multiple_entities(self):
        """Test creating a BronFormat object with multiple entities."""
        bf = BronFormat(
            GMN={"gmn1": {"Adm": {}}},
            GMW={"gmw1": {"Well": {}}},
            GLD={"gld1": {"Source": {}}},
        )
        assert bf.GMN is not None
        assert bf.GMW is not None
        assert bf.GLD is not None
        assert len(bf.GMN) == 1
        assert len(bf.GMW) == 1
        assert len(bf.GLD) == 1

    def test_repr_empty(self):
        """Test __repr__ with empty BronFormat."""
        bf = BronFormat()
        repr_str = repr(bf)
        assert "BronFormat()" == repr_str

    def test_repr_with_entities(self):
        """Test __repr__ with populated entities."""
        bf = BronFormat(GMN={"gmn1": {}}, GLD={"gld1": {}}, BHR={"bhr1": {}})
        repr_str = repr(bf)
        assert "BronFormat(" in repr_str
        assert "GMN" in repr_str
        assert "GLD" in repr_str
        assert "BHR" in repr_str
        # Should be alphabetically ordered
        assert repr_str == "BronFormat(BHR, GLD, GMN)"

    def test_repr_with_all_entities(self):
        """Test __repr__ with all entities populated."""
        bf = BronFormat(
            GMN={"gmn1": {}},
            GMW={"gmw1": {}},
            GLD={"gld1": {}},
            GAR={"gar1": {}},
            BHR={"bhr1": {}},
            GUF={"guf1": {}},
            GPD={"gpd1": {}},
            Proces={"proc1": {}},
            IN={"in1": {}},
            QC={"qc1": {}},
            File={"file1": {}},
            GIS={"gis1": {}},
            Cache={"cache1": {}},
            SAD={"sad1": {}},
        )
        repr_str = repr(bf)
        # All entities should be listed
        assert "GMN" in repr_str
        assert "GMW" in repr_str
        assert "GLD" in repr_str
        assert "GAR" in repr_str
        assert "BHR" in repr_str
        assert "GUF" in repr_str
        assert "GPD" in repr_str

    def test_to_dict_empty(self):
        """Test to_dict with empty BronFormat."""
        bf = BronFormat()
        result = bf.to_dict()
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_to_dict_with_data(self):
        """Test to_dict with populated data."""
        bf = BronFormat(
            GMN={"gmn1": {"Adm": {"name": "test"}}},
            GLD={"gld1": {"Source": {"Measurements": []}}},
        )
        result = bf.to_dict()
        assert isinstance(result, dict)
        assert len(result) == 2
        assert "GMN" in result
        assert "GLD" in result
        assert result["GMN"] == {"gmn1": {"Adm": {"name": "test"}}}
        assert result["GLD"] == {"gld1": {"Source": {"Measurements": []}}}

    def test_to_dict_excludes_none_attributes(self):
        """Test that to_dict excludes None attributes."""
        bf = BronFormat(GMN={"gmn1": {}}, GMW=None, GLD={"gld1": {}})
        result = bf.to_dict()
        assert "GMN" in result
        assert "GMW" not in result
        assert "GLD" in result
        assert len(result) == 2

    def test_print_empty(self, capsys):
        """Test print method with empty BronFormat."""
        bf = BronFormat()
        bf.print()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_with_data(self, capsys):
        """Test print method with populated data."""
        bf = BronFormat(GMN={"gmn1": {"Adm": {"name": "test"}}})
        bf.print()
        captured = capsys.readouterr()
        assert "GMN/ (group)" in captured.out
        assert "gmn1/ (group)" in captured.out
        assert "Adm/ (group)" in captured.out
        assert "name: str = test" in captured.out

    def test_print_nested_structure(self, capsys):
        """Test print method with deeply nested structure."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Adm": {"BROID": "gld1", "name": "Level Data"},
                    "Source": {
                        "Measurements": [
                            {"DateTime": "2023-01-01", "RawValue": 10.5},
                            {"DateTime": "2023-01-02", "RawValue": 11.2},
                        ]
                    },
                }
            }
        )
        bf.print()
        captured = capsys.readouterr()
        assert "GLD/ (group)" in captured.out
        assert "gld1/ (group)" in captured.out
        assert "Adm/ (group)" in captured.out
        assert "Source/ (group)" in captured.out
        assert "Measurements: list with 2 items" in captured.out

    def test_print_with_indent(self, capsys):
        """Test print method with custom indentation."""
        bf = BronFormat(GMN={"gmn1": {"Adm": {"name": "test"}}})
        bf.print(indent=1)
        captured = capsys.readouterr()
        # With indent=1, the prefix should be 2 spaces
        _ = captured.out.strip().split("\n")
        assert "  GMN/ (group)" in captured.out


class TestGetEntityIdFromRow:
    """Tests for the _get_entity_id_from_row helper function."""

    def test_entity_id_from_entity_id_column(self):
        """Test extracting ID from EntityID column."""
        row = pd.Series({"EntityID": "test123", "other": "value"})
        result = _get_entity_id_from_row(row, "SomeEntity")
        assert result == "test123"

    def test_entity_id_from_specific_id_column(self):
        """Test extracting ID from entity-specific ID column."""
        row = pd.Series({"GMNID": "gmn123", "other": "value"})
        result = _get_entity_id_from_row(row, "GMN")
        assert result == "gmn123"

    def test_entity_id_from_broid_column(self):
        """Test extracting ID from BROID column."""
        row = pd.Series({"BROID": "broid123", "other": "value"})
        result = _get_entity_id_from_row(row, "SomeEntity")
        assert result == "broid123"

    def test_entity_id_from_generic_id_column(self):
        """Test extracting ID from generic ID column."""
        row = pd.Series({"ID": "id123", "other": "value"})
        result = _get_entity_id_from_row(row, "SomeEntity")
        assert result == "id123"

    def test_entity_id_na_values_skipped(self):
        """Test that NaN values are skipped."""
        row = pd.Series({"EntityID": pd.NA, "BROID": pd.NA, "ID": pd.NA})
        result = _get_entity_id_from_row(row, "SomeEntity")
        assert result is None

    def test_entity_id_priority_order(self):
        """Test that EntityID has priority over other ID columns."""
        row = pd.Series(
            {"EntityID": "entity123", "BROID": "broid456", "GMNID": "gmn789"}
        )
        result = _get_entity_id_from_row(row, "GMN")
        assert result == "entity123"

    def test_entity_id_no_id_columns(self):
        """Test with row that has no ID columns."""
        row = pd.Series({"col1": "value1", "col2": "value2"})
        result = _get_entity_id_from_row(row, "SomeEntity")
        assert result is None

    def test_entity_id_empty_row(self):
        """Test with empty row."""
        row = pd.Series(dtype=object)
        result = _get_entity_id_from_row(row, "SomeEntity")
        assert result is None

    def test_entity_id_numeric_id(self):
        """Test with numeric ID that gets converted to string."""
        row = pd.Series({"BROID": 12345})
        result = _get_entity_id_from_row(row, "SomeEntity")
        assert result == "12345"
        assert isinstance(result, str)


class TestConvertFromDataframes:
    """Tests for the _convert_from_dataframes function."""

    def test_convert_empty_dataframes(self):
        """Test conversion with empty DataFrames."""
        metadata_df = pd.DataFrame()
        data_df = pd.DataFrame()
        result = _convert_from_dataframes(metadata_df, data_df)
        assert isinstance(result, BronFormat)
        assert result.to_dict() == {}

    def test_convert_metadata_only(self):
        """Test conversion with only metadata DataFrame."""
        # Create a simple metadata DataFrame
        metadata_df = pd.DataFrame(
            {
                "Entity": ["GLD", "GLD"],
                "SubEntity": ["Adm", "Source"],
                "BROID": ["gld1", "gld1"],
                "BROID_SubEntity": [None, None],
                "name": ["Level Data", None],
                "other": [None, "value"],
            }
        )
        metadata_df.index = pd.MultiIndex.from_arrays(
            [
                metadata_df["Entity"],
                metadata_df["SubEntity"],
                metadata_df["BROID"],
                metadata_df["BROID_SubEntity"],
            ],
            names=["Entity", "SubEntity", "BROID", "BROID_SubEntity"],
        )
        metadata_df = metadata_df[["name", "other"]]

        data_df = pd.DataFrame()
        result = _convert_from_dataframes(metadata_df, data_df)

        assert isinstance(result, BronFormat)
        assert result.GLD is not None
        assert "gld1" in result.GLD
        assert "Adm" in result.GLD["gld1"]
        assert "Source" in result.GLD["gld1"]

    def test_convert_with_time_series_data(self):
        """Test conversion with time series data."""
        # Create metadata DataFrame
        metadata_df = pd.DataFrame(
            {
                "Entity": ["GLD"],
                "SubEntity": ["Adm"],
                "BROID": ["gld1"],
                "BROID_SubEntity": [None],
                "name": ["Level Data"],
            }
        )
        metadata_df.index = pd.MultiIndex.from_arrays(
            [
                metadata_df["Entity"],
                metadata_df["SubEntity"],
                metadata_df["BROID"],
                metadata_df["BROID_SubEntity"],
            ],
            names=["Entity", "SubEntity", "BROID", "BROID_SubEntity"],
        )
        metadata_df = metadata_df[["name"]]

        # Create data DataFrame with time series
        data_df = pd.DataFrame(
            {"DateTime": ["2023-01-01", "2023-01-02"], "RawValue": [10.5, 11.2]}
        )
        data_df.index = pd.MultiIndex.from_arrays(
            [["GLD"], ["Source"], ["gld1"], [None]],
            names=["Entity", "SubEntity", "BROID", "BROID_SubEntity"],
        )

        result = _convert_from_dataframes(metadata_df, data_df)

        assert result.GLD is not None
        assert "gld1" in result.GLD
        assert "Source" in result.GLD["gld1"]
        assert "Measurements" in result.GLD["gld1"]["Source"]
        measurements = result.GLD["gld1"]["Source"]["Measurements"]
        assert len(measurements) == 2
        assert measurements[0]["DateTime"] == "2023-01-01"
        assert measurements[0]["RawValue"] == 10.5

    def test_convert_all_nan_broids(self):
        """Test conversion when all BROIDs are NaN."""
        metadata_df = pd.DataFrame(
            {
                "Entity": ["GMN", "GMN"],
                "SubEntity": ["Adm", "Network"],
                "BROID": [pd.NA, pd.NA],
                "BROID_SubEntity": [None, None],
                "GMNID": ["gmn123", None],
                "name": ["Network 1", "Some value"],
            }
        )
        metadata_df.index = pd.MultiIndex.from_arrays(
            [
                metadata_df["Entity"],
                metadata_df["SubEntity"],
                metadata_df["BROID"],
                metadata_df["BROID_SubEntity"],
            ],
            names=["Entity", "SubEntity", "BROID", "BROID_SubEntity"],
        )
        metadata_df = metadata_df[["GMNID", "name"]]

        data_df = pd.DataFrame()
        result = _convert_from_dataframes(metadata_df, data_df)

        # Should still create structure using extracted ID
        assert result.GMN is not None or len(result.to_dict()) > 0

    def test_convert_multiple_entities(self):
        """Test conversion with multiple entity types."""
        metadata_df = pd.DataFrame(
            {
                "Entity": ["GLD", "BHR", "GLD"],
                "SubEntity": ["Adm", "Borehole", "Source"],
                "BROID": ["gld1", "bhr1", "gld1"],
                "BROID_SubEntity": [None, None, None],
                "name": ["GLD 1", "BHR 1", None],
            }
        )
        metadata_df.index = pd.MultiIndex.from_arrays(
            [
                metadata_df["Entity"],
                metadata_df["SubEntity"],
                metadata_df["BROID"],
                metadata_df["BROID_SubEntity"],
            ],
            names=["Entity", "SubEntity", "BROID", "BROID_SubEntity"],
        )
        metadata_df = metadata_df[["name"]]

        data_df = pd.DataFrame()
        result = _convert_from_dataframes(metadata_df, data_df)

        assert result.GLD is not None
        assert result.BHR is not None
        assert "gld1" in result.GLD
        assert "bhr1" in result.BHR

    def test_convert_internal_columns_excluded(self):
        """Test that internal columns are excluded from conversion."""
        metadata_df = pd.DataFrame(
            {
                "Entity": ["GLD"],
                "SubEntity": ["Adm"],
                "BROID": ["gld1"],
                "BROID_SubEntity": [None],
                "EntityID": ["should_be_excluded"],
                "SubEntityID": ["should_be_excluded"],
                "name": ["Level Data"],
            }
        )
        metadata_df.index = pd.MultiIndex.from_arrays(
            [
                metadata_df["Entity"],
                metadata_df["SubEntity"],
                metadata_df["BROID"],
                metadata_df["BROID_SubEntity"],
            ],
            names=["Entity", "SubEntity", "BROID", "BROID_SubEntity"],
        )
        metadata_df = metadata_df[["EntityID", "SubEntityID", "name"]]

        data_df = pd.DataFrame()
        result = _convert_from_dataframes(metadata_df, data_df)

        assert result.GLD is not None
        assert "gld1" in result.GLD
        assert "Adm" in result.GLD["gld1"]
        # EntityID and SubEntityID should be excluded
        assert "EntityID" not in result.GLD["gld1"]["Adm"]
        assert "SubEntityID" not in result.GLD["gld1"]["Adm"]
        assert "name" in result.GLD["gld1"]["Adm"]


class TestReadBronformat:
    """Additional tests for read_bronformat function (beyond test_reader.py)."""

    def test_read_bronformat_returns_bronformat(self):
        """Test that read_bronformat returns a BronFormat instance."""
        data_path = Path(__file__).parent / "data"
        result = read_bronformat(data_path / "gld_bhr.hdf5")
        assert isinstance(result, BronFormat)

    def test_read_bronformat_to_dict_method(self):
        """Test that the result has working to_dict method."""
        data_path = Path(__file__).parent / "data"
        result = read_bronformat(data_path / "gld_bhr.hdf5")
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)

    def test_read_bronformat_repr_method(self):
        """Test that the result has working repr method."""
        data_path = Path(__file__).parent / "data"
        result = read_bronformat(data_path / "gld_bhr.hdf5")
        repr_str = repr(result)
        assert isinstance(repr_str, str)
        assert "BronFormat(" in repr_str

    def test_read_bronformat_print_method(self, capsys):
        """Test that the result has working print method."""
        data_path = Path(__file__).parent / "data"
        result = read_bronformat(data_path / "gld_bhr.hdf5")
        result.print()
        captured = capsys.readouterr()
        assert len(captured.out) > 0
        # Should contain some group indicators
        assert "/ (group)" in captured.out

    def test_read_bronformat_path_object(self):
        """Test read_bronformat with Path object."""
        data_path = Path(__file__).parent / "data"
        result = read_bronformat(Path(data_path / "gld_bhr.hdf5"))
        assert isinstance(result, BronFormat)

    def test_read_bronformat_string_path(self):
        """Test read_bronformat with string path."""
        data_path = Path(__file__).parent / "data"
        result = read_bronformat(str(data_path / "gld_bhr.hdf5"))
        assert isinstance(result, BronFormat)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_bronformat_all_none_to_dict(self):
        """Test to_dict when all attributes are None."""
        bf = BronFormat()
        result = bf.to_dict()
        assert result == {}

    def test_get_entity_id_with_mixed_na_and_values(self):
        """Test _get_entity_id_from_row with mix of NaN and actual values."""
        row = pd.Series(
            {
                "EntityID": pd.NA,
                "BROID": pd.NA,
                "CustomID": "actual_id",
                "other": "value",
            }
        )
        result = _get_entity_id_from_row(row, "SomeEntity")
        assert result == "actual_id"

    def test_convert_dataframes_with_na_values(self):
        """Test _convert_from_dataframes with NaN values in data."""
        metadata_df = pd.DataFrame(
            {
                "Entity": ["GLD"],
                "SubEntity": ["Adm"],
                "BROID": ["gld1"],
                "BROID_SubEntity": [None],
                "name": ["Level Data"],
                "optional": [pd.NA],
            }
        )
        metadata_df.index = pd.MultiIndex.from_arrays(
            [
                metadata_df["Entity"],
                metadata_df["SubEntity"],
                metadata_df["BROID"],
                metadata_df["BROID_SubEntity"],
            ],
            names=["Entity", "SubEntity", "BROID", "BROID_SubEntity"],
        )
        metadata_df = metadata_df[["name", "optional"]]

        data_df = pd.DataFrame()
        result = _convert_from_dataframes(metadata_df, data_df)

        assert result.GLD is not None
        assert "gld1" in result.GLD
        assert "Adm" in result.GLD["gld1"]
        assert "name" in result.GLD["gld1"]["Adm"]
        # NaN values should be excluded
        assert "optional" not in result.GLD["gld1"]["Adm"]


class TestPerformance:
    """Performance and scalability tests."""

    def test_bronformat_repr_large_structure(self):
        """Test repr with large structure (many entities)."""
        # Create a BronFormat with all possible entities
        bf = BronFormat(
            GMN={f"gmn{i}": {} for i in range(10)},
            GMW={f"gmw{i}": {} for i in range(10)},
            GLD={f"gld{i}": {} for i in range(10)},
            GAR={f"gar{i}": {} for i in range(10)},
            BHR={f"bhr{i}": {} for i in range(10)},
        )
        # Should complete quickly
        repr_str = repr(bf)
        assert "BronFormat(" in repr_str
        assert "GMN" in repr_str

    def test_bronformat_to_dict_large_structure(self):
        """Test to_dict with large nested structure."""
        bf = BronFormat(
            GLD={
                f"gld{i}": {
                    "Adm": {f"key{j}": f"value{j}" for j in range(10)},
                    "Source": {"Measurements": [{f"ts{k}": k} for k in range(100)]},
                }
                for i in range(5)
            }
        )
        result = bf.to_dict()
        assert isinstance(result, dict)
        assert "GLD" in result
        assert len(result["GLD"]) == 5
