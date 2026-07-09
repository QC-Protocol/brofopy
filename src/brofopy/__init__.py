"""brofopy - read Bronformat data as nested dictionaries."""

from brofopy.bronformat import read_bronformat
from brofopy.ext.hpd import to_obscollection

from ._version import __version__, show_versions

__all__ = ["read_bronformat", "__version__", "show_versions"]
