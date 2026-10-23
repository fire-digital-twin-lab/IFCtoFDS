"""Approved, content-bound reference cases; candidates never approve themselves."""

from ifc_to_fds.modules.reference.infrastructure.bundle_io import (
    FILES,
    bundle_digest,
    create_candidate,
    inspect_case,
    resolve_case,
    resolve_sources,
)
from ifc_to_fds.modules.reference.application.parity import golden_gate
from ifc_to_fds.modules.reference.application.projections import (
    serialized_geometry,
    source_signature,
)

__all__ = [
    "FILES",
    "bundle_digest",
    "create_candidate",
    "inspect_case",
    "resolve_case",
    "resolve_sources",
    "source_signature",
    "serialized_geometry",
    "golden_gate",
]
