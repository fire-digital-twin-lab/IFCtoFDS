"""Compatibility import for ifc_to_fds.runtime.normalization."""

from importlib import import_module as _import_module
import sys as _sys
_sys.modules[__name__] = _import_module("ifc_to_fds.runtime.normalization")
