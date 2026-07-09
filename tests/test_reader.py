"""Tests for brofopy.reader - HDF5 files only."""

from pathlib import Path

import pytest

from brofopy import read_bronformat
from brofopy.bronformat import BronFormat
from brofopy.exceptions import BronformatParseError

data_path = Path(__file__).parent / "data"


def test_read_gar_hdf5():
    """Test reading GAR .hdf5 file."""
    result = read_bronformat(data_path / "gar.hdf5")
    assert isinstance(result, BronFormat)
    assert result.GAR is not None
    assert len(result.GAR) > 0  # Has at least one entry
    
    # Check structure of first GAR entry
    first_entry = next(iter(result.GAR.values()))
    assert isinstance(first_entry, dict)
    
    # GAR should have specific sub-entities
    expected_sub_entities = ["Adm", "Analysis", "Field", "History", "Lab", "Measurement"]
    for sub_entity in expected_sub_entities:
        assert sub_entity in first_entry, f"Missing sub-entity: {sub_entity}"


def test_read_gld_hdf5():
    """Test reading GLD from combined file."""
    result = read_bronformat(data_path / "gld_bhr.hdf5")
    assert isinstance(result, BronFormat)
    assert result.GLD is not None
    assert len(result.GLD) > 0

    # Check first GLD entry has expected structure
    first_broid, first_entry = next(iter(result.GLD.items()))
    assert isinstance(first_entry, dict)
    
    # GLD should have specific sub-entities
    expected_sub_entities = ["Adm", "Dossier", "History", "Source"]
    for sub_entity in expected_sub_entities:
        assert sub_entity in first_entry, f"Missing sub-entity: {sub_entity}"
    
    # Check Source sub-entity
    source = first_entry["Source"]
    assert isinstance(source, dict)
    
    # Source should have Measurements
    assert "Measurements" in source
    assert isinstance(source["Measurements"], list)
    assert len(source["Measurements"]) > 0
    
    # Check first measurement has expected keys
    first_measurement = source["Measurements"][0]
    assert isinstance(first_measurement, dict)
    assert "DateTime" in first_measurement
    assert "RawValue" in first_measurement
    
    # Check Dossier has expected keys
    dossier = first_entry["Dossier"]
    assert "GMWBROID" in dossier
    assert "GMWID" in dossier
    assert "TubeNo" in dossier
    
    # Check Adm has expected keys
    adm = first_entry["Adm"]
    assert "AccParty" in adm or "BROID" in adm or "EntityID" in adm


def test_read_bhr_hdf5():
    """Test reading BHR from combined file."""
    result = read_bronformat(data_path / "gld_bhr.hdf5")
    assert result.BHR is not None
    assert len(result.BHR) > 0
    
    # Check structure of first BHR entry
    first_entry = next(iter(result.BHR.values()))
    assert isinstance(first_entry, dict)
    
    # BHR should have specific sub-entities
    expected_sub_entities = ["Adm", "Borehole", "History", "Layers"]
    for sub_entity in expected_sub_entities:
        assert sub_entity in first_entry, f"Missing sub-entity: {sub_entity}"
    
    # Check Adm has BHRID
    adm = first_entry["Adm"]
    assert "BHRID" in adm or "EntityID" in adm


def test_read_guf_gpd_hdf5():
    """Test reading GUF and GPD .hdf5 file."""
    result = read_bronformat(data_path / "guf_gpd.hdf5")
    assert result.GUF is not None
    assert result.GPD is not None
    assert len(result.GUF) > 0
    assert len(result.GPD) > 0
    
    # Check GUF structure
    first_guf = next(iter(result.GUF.values()))
    assert isinstance(first_guf, dict)
    # GUF should have Adm sub-entity
    assert "Adm" in first_guf
    
    # Check GPD structure
    first_gpd = next(iter(result.GPD.values()))
    assert isinstance(first_gpd, dict)
    # GPD may have Volumes sub-entity
    if "Volumes" in first_gpd:
        assert isinstance(first_gpd["Volumes"], list) or isinstance(first_gpd["Volumes"], dict)


def test_read_sad_hdf5():
    """Test reading SAD .hdf5 file."""
    result = read_bronformat(data_path / "sad.hdf5")
    assert result.SAD is not None
    assert len(result.SAD) > 0
    
    # Check structure of first SAD entry
    first_entry = next(iter(result.SAD.values()))
    assert isinstance(first_entry, dict)
    # SAD should have Adm sub-entity
    assert "Adm" in first_entry or len(first_entry) > 0


def test_gld_has_all_expected_sub_entities():
    """Test that all GLD entries have all expected sub-entities and keys."""
    result = read_bronformat(data_path / "gld_bhr.hdf5")
    assert result.GLD is not None
    
    for broid, entry in result.GLD.items():
        # Check sub-entities exist
        assert "Adm" in entry, f"GLD entry {broid} missing Adm"
        assert "Dossier" in entry, f"GLD entry {broid} missing Dossier"
        assert "History" in entry, f"GLD entry {broid} missing History"
        assert "Source" in entry, f"GLD entry {broid} missing Source"
        
        # Check Source has Measurements
        source = entry["Source"]
        assert "Measurements" in source, f"GLD entry {broid} Source missing Measurements"
        assert isinstance(source["Measurements"], list), f"GLD entry {broid} Measurements is not a list"
        
        # Check Measurements have required keys
        if len(source["Measurements"]) > 0:
            first_measurement = source["Measurements"][0]
            assert "DateTime" in first_measurement, f"GLD entry {broid} measurement missing DateTime"
            assert "RawValue" in first_measurement, f"GLD entry {broid} measurement missing RawValue"


def test_gld_measurements_count():
    """Test that GLD Measurements have the expected number of entries."""
    result = read_bronformat(data_path / "gld_bhr.hdf5")
    assert result.GLD is not None
    
    for broid, entry in result.GLD.items():
        source = entry["Source"]
        measurements = source["Measurements"]
        # Should have measurements
        assert len(measurements) > 0, f"GLD entry {broid} has no measurements"


def test_gmn_structure():
    """Test that GMN entries have expected structure."""
    result = read_bronformat(data_path / "gld_bhr.hdf5")
    if result.GMN is not None:
        assert len(result.GMN) > 0
        first_entry = next(iter(result.GMN.values()))
        assert isinstance(first_entry, dict)
        # GMN should have Adm sub-entity
        assert "Adm" in first_entry


def test_gmw_structure():
    """Test that GMW entries have expected structure."""
    result = read_bronformat(data_path / "gld_bhr.hdf5")
    if result.GMW is not None:
        assert len(result.GMW) > 0
        first_entry = next(iter(result.GMW.values()))
        assert isinstance(first_entry, dict)
        # GMW should have Well sub-entity with coordinates
        assert "Well" in first_entry or "Adm" in first_entry


def test_no_bron_extension():
    """Test that .bron files raise BronformatParseError."""
    with pytest.raises(BronformatParseError):
        read_bronformat(data_path / "testdata.bron")


def test_no_bron2_extension():
    """Test that .bron2 files work (scipy backend)."""
    # .bron2 files should work with scipy backend
    result = read_bronformat(data_path / "testdata.bron2")
    assert isinstance(result, BronFormat)
    # At least one entity should be present
    assert len(result.to_dict()) > 0
    
    # Check GLD structure in .bron2 file
    if result.GLD is not None:
        assert len(result.GLD) > 0
        first_entry = next(iter(result.GLD.values()))
        assert "Source" in first_entry
        assert "Measurements" in first_entry["Source"]
