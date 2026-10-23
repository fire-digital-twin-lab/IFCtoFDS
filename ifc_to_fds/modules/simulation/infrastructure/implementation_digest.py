"""Bind certificates to actual implementation bytes, never compatibility aliases."""

import hashlib
from pathlib import Path

def adapter_digest():
    from importlib.util import find_spec

    files = [
        Path(find_spec(module).origin)
        for module in (
            "ifc_to_fds.modules.simulation.application.boundary_policy",
            "ifc_to_fds.modules.simulation.application.mapping_policy",
            "ifc_to_fds.modules.fds.application.serializer",
            "ifc_to_fds.modules.verification.application.effective_obstructions",
            "ifc_to_fds.modules.verification.application.effective_multimesh",
            "ifc_to_fds.modules.verification.application.effective_topology",
            "ifc_to_fds.modules.geometry.algorithms.mesh",
            "ifc_to_fds.modules.geometry.algorithms.exact_predicates",
            "ifc_to_fds.modules.geometry.algorithms.metrics",
            "ifc_to_fds.modules.verification.application.boundary_certification",
            "ifc_to_fds.modules.verification.infrastructure.fds.solver_process",
            "ifc_to_fds.modules.verification.application.solver_completion",
            "ifc_to_fds.modules.verification.application.effective_openings",
            "ifc_to_fds.modules.verification.application.solver_surface",
            "ifc_to_fds.modules.verification.infrastructure.fds.bingeom",
        )
    ]
    return hashlib.sha256(
        "".join(p.read_text(encoding="utf-8") for p in files).encode()
    ).hexdigest()

