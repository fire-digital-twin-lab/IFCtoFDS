"""Server package with compatibility re-exports from ifc_to_fds.server module."""

import importlib.machinery
import importlib.util
import os
import sys

from .job_repository import JobRepository

__all__ = ["JobRepository"]

_server_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server.py")
if os.path.isfile(_server_py):
    _loader = importlib.machinery.SourceFileLoader("ifc_to_fds.server", _server_py)
    _spec = importlib.util.spec_from_loader("ifc_to_fds.server", _loader)
    if _spec:
        _mod = importlib.util.module_from_spec(_spec)
        _mod.__package__ = "ifc_to_fds"
        _mod.__path__ = [os.path.dirname(__file__)]
        _mod.JobRepository = JobRepository
        sys.modules["ifc_to_fds.server"] = _mod
        _loader.exec_module(_mod)
        for _k, _v in _mod.__dict__.items():
            if not _k.startswith("__"):
                globals()[_k] = _v
                if _k not in __all__:
                    __all__.append(_k)
