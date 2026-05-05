"""Tests for bronformat_reader.reader."""

import pytest

from bronformat_reader.reader import read_bronformat


def test_read_bronformat_raises_not_implemented() -> None:
    """read_bronformat should raise NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        read_bronformat("dummy_path.bro")
