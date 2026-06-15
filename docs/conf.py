# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from __future__ import annotations

import sys
from importlib.metadata import version as _version
from pathlib import Path

import django
from django.conf import settings

sys.path.append(str((Path(__file__).parent / "_ext").resolve()))

# Configure Django so autodoc can import and introspect the source modules.
if not settings.configured:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth"],
        DATABASES={},
    )
    django.setup()

project = "Django MongoDB Extensions"
copyright = "2025, The MongoDB Python Team"
author = "The MongoDB Python Team"
release = _version("django_mongodb_extensions")

add_module_names = False
toc_object_entries = False

extensions = [
    "djangodocs",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
]

autodoc_mock_imports = [
    "bson",
    "debug_toolbar",
    "django.views.decorators.csrf",
    "django_mongodb_backend",
    "pymongo",
    "rest_framework",
]

exclude_patterns = ["_build"]

intersphinx_mapping = {
    "django": (
        "https://docs.djangoproject.com/en/stable/",
        "https://docs.djangoproject.com/en/stable/_objects/",
    ),
    "django-mongodb-backend": (
        "https://django-mongodb-backend.readthedocs.io/en/latest/",
        None,
    ),
    "python": ("https://docs.python.org/3/", None),
}

html_theme = "furo"

copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True
