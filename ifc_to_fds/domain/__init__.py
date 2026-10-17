"""Domain layer for IFCtoFDS Verified Core.

Contains core business rules, entity models, value objects, and domain services.
Pure domain logic: independent of external frameworks (FastAPI, IfcOpenShell, FDS, filesystem).
"""

from . import bim, mapping, mep, reference, scope, source, validation, version
from .version import SCHEMA_VERSION

__all__ = [
    "SCHEMA_VERSION",
    "bim",
    "mapping",
    "mep",
    "reference",
    "scope",
    "source",
    "validation",
    "version",
]
