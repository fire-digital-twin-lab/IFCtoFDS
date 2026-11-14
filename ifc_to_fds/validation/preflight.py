"""Shared source-topology eligibility and policy for both audit entry points."""

from __future__ import annotations

from typing import Any, Dict

from ifc_to_fds.domain.mapping.enums import MappingStrategy
from ifc_to_fds.domain.scope.model import ScopeDecision
from ifc_to_fds.geometry.mesh import (
    inspect_mesh_quality,
    mesh_digest,
    prefetch_self_intersection,
    self_intersection_evidence,
    valid_solid,
)


def source_topology_preflight(model) -> Dict[str, Dict[str, Any]]:
    """Return fail-closed topology evidence for every in-scope physical source mesh.

    A closed manifold with positive signed volume is necessary but not sufficient:
    a self-intersecting solid is also invalid for downstream enclosure/opening/solver
    gates. Numerical uncertainty in the self-intersection oracle blocks dependent
    gates as INCONCLUSIVE rather than being silently treated as clean.
    """

    evidence: Dict[str, Dict[str, Any]] = {}
    # Heavy meshes are independent of each other: scan them in parallel, then the loop below reads the cache.
    prefetch_self_intersection(
        e.mesh
        for e in model.elements
        if e.role == "PHYSICAL"
        and e.scope_decision in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)
        and e.mesh
        and e.mapping_strategy != MappingStrategy.NONE
        and len(e.mesh.faces) >= 2000
        and valid_solid(e.mesh)
    )
    for element in model.elements:
        if (
            element.role != "PHYSICAL"
            or element.scope_decision
            not in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)
            or not element.mesh
        ):
            continue

        quality = inspect_mesh_quality(element.mesh)
        if not valid_solid(element.mesh):
            evidence[element.entity_key] = {
                "status": "FAIL",
                "reason": "INVALID_SOLID",
                "mesh_quality": quality,
            }
            continue

        if element.mapping_strategy == MappingStrategy.NONE:
            # Never exported to FDS: a self-intersection cannot reach the solver, and scanning
            # thousands of reference meshes (MEP) is the most expensive part of the preflight.
            evidence[element.entity_key] = {"status": "PASS", "reason": "REFERENCE_ONLY"}
            continue

        intersection = self_intersection_evidence(element.mesh)
        if intersection["status"] == "CONFIRMED":
            evidence[element.entity_key] = {
                "status": "FAIL",
                "reason": "SELF_INTERSECTION",
                "mesh_quality": quality,
                "self_intersection": intersection,
                "mesh_sha256": mesh_digest(element.mesh),  # to cite in accepted_source_defects
            }
        elif intersection["status"] == "ACCEPTED_DEFECT":
            evidence[element.entity_key] = {
                "status": "PASS",
                "reason": "ACCEPTED_DEFECT",
                "self_intersection": intersection,
            }
        elif intersection["status"] == "UNCERTAIN":
            evidence[element.entity_key] = {
                "status": "INCONCLUSIVE",
                "reason": "SELF_INTERSECTION_UNCERTAIN",
                "mesh_quality": quality,
                "self_intersection": intersection,
            }
        else:
            evidence[element.entity_key] = {
                "status": "PASS",
                "reason": "CLEAN",
                "self_intersection": intersection,
            }
    return evidence


def source_topology_blockers(evidence: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return only source-topology entries that cannot authorize dependent gates."""

    return {
        key: item
        for key, item in evidence.items()
        if item.get("status") in ("FAIL", "INCONCLUSIVE")
    }


def invalid_source_solids(model):
    """Preserve the historical manifold/volume compatibility contract.

    Self-intersection is handled by source_topology_preflight(). Keeping this
    function stable prevents legacy consumers from silently changing diagnostics.
    """

    return [
        element.entity_key
        for element in model.elements
        if element.role == "PHYSICAL"
        and element.scope_decision
        in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)
        and element.mesh
        and not valid_solid(element.mesh)
    ]


def comparison_summary(parsed, solids, invalid, *, mode, verified, attempted, completed,
                       skipped, failed, inconclusive, deviated):
    """Use one accounting contract for attempted, measured and withheld solids."""
    primitives = parsed.primitives
    return (
        dict(mode=mode, attempted_entities=sorted(attempted), completed_entities=sorted(completed),
             skipped_for_source_errors=sorted(skipped), failed_entities=sorted(failed),
             inconclusive_entities=sorted(inconclusive)),
        dict(entities=len(solids), primitives=len(primitives),
             obst=sum(p.kind == "OBST" for p in primitives), geom=sum(p.kind == "GEOM" for p in primitives),
             verified_entities=verified, comparisons_skipped_for_source_errors=bool(skipped),
             comparison_mode=mode, attempted_entities=len(attempted), compared_entities=len(completed),
             deviated_entities=len(deviated), failed_comparison_entities=len(failed),
             inconclusive_comparison_entities=len(inconclusive), not_compared_entities=len(set(solids) - completed),
             skipped_for_source_errors=len(skipped), source_invalid_entities=len(invalid)),
    )
