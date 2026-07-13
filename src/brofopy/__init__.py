"""brofopy - read Bronformat data as nested dictionaries."""

from brofopy.bronformat import BronFormat
from brofopy.ext.hpd import to_obscollection
from brofopy.ext.pd import to_dataframe
from brofopy.reader import read_bronformat

from ._version import __version__, show_versions

__all__ = [
    "read_bronformat",
    "BronFormat",
    "to_obscollection",
    "to_dataframe",
    "__version__",
    "show_versions",
]
