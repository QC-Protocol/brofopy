"""Tests for brofopy.bronformat module.

Tests the BronFormat class and its methods.
"""

from pathlib import Path

import pandas as pd
import pytest

from brofopy import read_bronformat
from brofopy.bronformat import BronFormat

data_path = Path(__file__).parent / "data"


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
                            {"DateTime": 738189.0, "RawValue": 10.5},
                            {"DateTime": 738190.0, "RawValue": 11.2},
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
        assert "  GMN/ (group)" in captured.out


class TestFromFile:
    """Tests for the from_file class method."""

    def test_from_file_hdf5(self):
        """Test from_file with HDF5 file."""
        result = BronFormat.from_file(data_path / "gld_bhr.hdf5")
        assert isinstance(result, BronFormat)
        assert result.GLD is not None
        assert len(result.GLD) > 0

    def test_from_file_bron2(self):
        """Test from_file with .bron2 file."""
        result = BronFormat.from_file(data_path / "testdata.bron2")
        assert isinstance(result, BronFormat)
        # At least one entity should be present
        assert len(result.to_dict()) > 0

    def test_from_file_with_path_object(self):
        """Test from_file with Path object."""
        result = BronFormat.from_file(Path(data_path / "gld_bhr.hdf5"))
        assert isinstance(result, BronFormat)

    def test_from_file_with_string_path(self):
        """Test from_file with string path."""
        result = BronFormat.from_file(str(data_path / "gld_bhr.hdf5"))
        assert isinstance(result, BronFormat)


class TestToDataframe:
    """Tests for the to_dataframe method."""

    def test_to_dataframe_empty(self):
        """Test to_dataframe with empty BronFormat."""
        bf = BronFormat()
        result = bf.to_dataframe()
        assert isinstance(result, pd.DataFrame)
        assert result.empty or len(result) == 0

    def test_to_dataframe_with_measurements(self):
        """Test to_dataframe with GLD data containing measurements."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Adm": {"BROID": "gld1", "name": "Level Data"},
                    "Source": {
                        "Measurements": [
                            {"DateTime": 738189.0, "RawValue": 10.5},
                            {"DateTime": 738190.0, "RawValue": 11.2},
                        ]
                    },
                }
            }
        )
        result = bf.to_dataframe()
        assert isinstance(result, pd.DataFrame)
        # Should have at least DateTime and RawValue columns
        assert "DateTime" in result.columns or len(result.columns) > 0
        # Should have 2 rows (one for each measurement)
        assert len(result) == 2

    def test_to_dataframe_from_file(self):
        """Test to_dataframe with real file data."""
        bf = read_bronformat(data_path / "gld_bhr.hdf5")
        result = bf.to_dataframe()
        assert isinstance(result, pd.DataFrame)
        # Should have some rows if there are measurements
        if bf.GLD is not None:
            # Count total measurements across all GLD entries
            total_measurements = 0
            for entry in bf.GLD.values():
                source = entry.get("Source", {})
                measurements = source.get("Measurements", [])
                total_measurements += len(measurements)
            if total_measurements > 0:
                assert len(result) >= total_measurements

    def test_to_dataframe_multiindex(self):
        """Test that to_dataframe creates MultiIndex."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Source": {
                        "Measurements": [
                            {"DateTime": 738189.0, "RawValue": 10.5},
                        ]
                    },
                }
            }
        )
        result = bf.to_dataframe()
        assert isinstance(result.index, pd.MultiIndex)
        assert "Entity" in result.index.names
        assert "BROID" in result.index.names

    def test_to_dataframe_multiple_entities(self):
        """Test to_dataframe with multiple entity types."""
        bf = BronFormat(
            GLD={
                "gld1": {
                    "Source": {
                        "Measurements": [
                            {"DateTime": 738189.0, "RawValue": 10.5},
                        ]
                    },
                }
            },
            GMW={"gmw1": {"Well": {"XCoordinate": 100.0, "YCoordinate": 200.0}}},
        )
        result = bf.to_dataframe()
        assert isinstance(result, pd.DataFrame)
        # Should have data from GLD measurements
        assert len(result) >= 1


class TestToObscollection:
    """Tests for the to_obscollection method."""

    def test_to_obscollection_empty(self):
        """Test to_obscollection with empty BronFormat."""
        bf = BronFormat()
        result = bf.to_obscollection(entity="GLD", name="Test")
        assert result.name == "Test"

    def test_to_obscollection_with_gld_data(self):
        """Test to_obscollection with GLD data."""
        bf = read_bronformat(data_path / "gld_bhr.hdf5")
        result = bf.to_obscollection(entity="GLD", name="TestCollection")
        assert result.name == "TestCollection"

    def test_to_obscollection_unsupported_entity(self):
        """Test to_obscollection with unsupported entity type."""
        bf = BronFormat(BHR={"bhr1": {"Borehole": {}}})
        # BHR is not a supported entity for to_obscollection
        with pytest.raises(ValueError, match="Unsupported entity type"):
            bf.to_obscollection(entity="BHR", name="Test")


class TestReadBronformat:
    """Tests for read_bronformat function."""

    def test_read_bronformat_returns_bronformat(self):
        """Test that read_bronformat returns a BronFormat instance."""
        result = read_bronformat(data_path / "gld_bhr.hdf5")
        assert isinstance(result, BronFormat)

    def test_read_bronformat_to_dict_method(self):
        """Test that the result has working to_dict method."""
        result = read_bronformat(data_path / "gld_bhr.hdf5")
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)

    def test_read_bronformat_repr_method(self):
        """Test that the result has working repr method."""
        result = read_bronformat(data_path / "gld_bhr.hdf5")
        repr_str = repr(result)
        assert isinstance(repr_str, str)
        assert "BronFormat(" in repr_str

    def test_read_bronformat_print_method(self, capsys):
        """Test that the result has working print method."""
        result = read_bronformat(data_path / "gld_bhr.hdf5")
        result.print()
        captured = capsys.readouterr()
        assert len(captured.out) > 0
        # Should contain some group indicators
        assert "/ (group)" in captured.out

    def test_read_bronformat_path_object(self):
        """Test read_bronformat with Path object."""
        result = read_bronformat(Path(data_path / "gld_bhr.hdf5"))
        assert isinstance(result, BronFormat)

    def test_read_bronformat_string_path(self):
        """Test read_bronformat with string path."""
        result = read_bronformat(str(data_path / "gld_bhr.hdf5"))
        assert isinstance(result, BronFormat)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_bronformat_all_none_to_dict(self):
        """Test to_dict when all attributes are None."""
        bf = BronFormat()
        result = bf.to_dict()
        assert result == {}


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
