"""Tests for bronformat_reader.brodata_ext."""

import pytest

from bronformat_reader.brodata_ext import from_brodata


def test_from_brodata_raises_not_implemented() -> None:
    """from_brodata should raise NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        from_brodata()
