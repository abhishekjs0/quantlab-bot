# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# -- Path setup --------------------------------------------------------------
# Add the project root to the path so Sphinx can find the modules
sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------
project = "QuantLab"
copyright = "2025, QuantLab Team"
author = "QuantLab Team"
release = "2.2.0"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",  # Automatic documentation from docstrings
    "sphinx.ext.viewcode",  # Add source code links
    "sphinx.ext.napoleon",  # Support for Google and NumPy style docstrings
    "sphinx.ext.intersphinx",  # Link to other project's documentation
    "sphinx_autodoc_typehints",  # Include type hints in documentation
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# -- Extension configuration -------------------------------------------------
# autodoc
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
}

# Type hints
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"
