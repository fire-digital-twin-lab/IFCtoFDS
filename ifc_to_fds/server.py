"""Compatibility import for the HTTP app and its configuration hooks."""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("ifc_to_fds.interfaces.http.app")
