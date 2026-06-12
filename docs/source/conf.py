"""Sphinx configuration for bronformat-reader documentation."""

import os
import sys

# Make the src/ layout visible to Sphinx autodoc
sys.path.insert(0, os.path.abspath("../../src"))

from brofopy._version import __version__

project = "brofopy"
author = "Trefoil Hydrology & Artesia Water"
release = __version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "myst_parser",
]

html_theme = "sphinx_rtd_theme"

templates_path = ["_templates"]
exclude_patterns = []
