# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import logging
import os
import sys
from datetime import date

import opthub_evaluator

sys.path.insert(0, os.path.abspath("../"))
logging.basicConfig()
logger = logging.getLogger(__name__)

# -- Project information -----------------------------------------------------

project = "Opthub Evaluator"
copyright = "{} SIG-RBP".format(date.today().year)
author = "Naoki Hamada"

# The full version, including alpha/beta/rc tags
release = version = opthub_evaluator.__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.githubpages",
    "sphinx.ext.intersphinx",
    "sphinx.ext.linkcode",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
]

# -- autodoc -----------------------------------------------------------------
autodoc_type_aliases = {}
autodoc_inherit_docstrings = True

# -- autosectionlabel --------------------------------------------------------
autosectionlabel_prefix_document = True

# -- doctest -----------------------------------------------------------------
# https://www.sphinx-doc.org/ja/master/usage/extensions/doctest.html#confval-doctest_global_setup
doctest_global_setup = """
import opthub_evaluator
"""
doctest_test_doctest_blocks = "default"

# -- intersphinx -------------------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]


# https://www.sphinx-doc.org/ja/master/usage/extensions/linkcode.html
# Resolve function for the linkcode extension.
def linkcode_resolve(domain, info):
    def find_source():
        # try to find the file and line number, based on code from numpy:
        # https://github.com/numpy/numpy/blob/master/doc/source/conf.py#L286
        obj = sys.modules[info["module"]]
        for part in info["fullname"].split("."):
            obj = getattr(obj, part)
        import inspect

        file = inspect.getsourcefile(obj)
        file = os.path.relpath(file, start=os.path.dirname(opthub_evaluator.__file__))
        source, lineno = inspect.getsourcelines(obj)
        return file, lineno, lineno + len(source) - 1

    if domain != "py" or not info["module"]:
        return None
    try:
        filename = "opthub_evaluator/%s#L%d-L%d" % find_source()
    except Exception as e:
        logger.warning(e)
        filename = info["module"].replace(".", "/") + ".py"
    tag = "master"  # if 'dev' in release else ('v' + release)
    return "https://github.com/opthub-org/opthub-evaluator/blob/%s/%s" % (tag, filename)
