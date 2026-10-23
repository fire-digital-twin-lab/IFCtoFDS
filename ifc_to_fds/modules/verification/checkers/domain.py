"""Compatibility alias for ifc_to_fds.modules.verification.application.checkers.domain."""

from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("ifc_to_fds.modules.verification.application.checkers.domain")
