"""Compatibility facade for boundary policy and its independent acceptance."""

from ifc_to_fds.modules.simulation.application.boundary_policy import (
    POLICY, EXACT_POLICY, VERSION, FIXTURES, adapter_digest,
    eligible_bounds, target_mesh, intersect_solid, exact_bounds,
)
from ifc_to_fds.modules.verification.application.boundary_acceptance import certificate_valid, finalize_boundary
