"""Shared source-topology eligibility and policy for both audit entry points."""

from __future__ import annotations

from typing import Any, Dict

from ifc_to_fds.domain.scope.model import ScopeDecision
from ifc_to_fds.geometry.mesh import (
    inspect_mesh_quality,
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
    for element in model.elements:
        if (
            element.role != "PHYSICAL"
            or element.scope_decision
            not in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)
            or not element.mesh
        ):
            continue

        quality = inspect_mesh_quality(element.mesh)
        if not (quality["finite"] and quality["is_closed_manifold"] and quality["positive_volume"]):
            evidence[element.entity_key] = {
                "status": "FAIL",
                "reason": "INVALID_SOLID",
                "mesh_quality": quality,
            }
            continue

        intersection = self_intersection_evidence(element.mesh)
        witness_kind = intersection.get("witness", {}).get("kind")
        if intersection["status"] == "CONFIRMED":
            invalid_winding = witness_kind == "SHELL_WINDING_MISMATCH"
            evidence[element.entity_key] = {
                "status": "FAIL",
                "reason": "INVALID_SHELL_WINDING" if invalid_winding else "SELF_INTERSECTION",
                "mesh_quality": quality,
                "self_intersection": intersection,
            }
        elif intersection["status"] == "UNCERTAIN":
            contact = witness_kind in {"COMPONENT_BOUNDARY_CONTACT", "COMPONENT_BOUNDARY_UNRESOLVED"}
            evidence[element.entity_key] = {
                "status": "INCONCLUSIVE",
                "reason": "SHELL_CONTACT" if contact else "SELF_INTERSECTION_UNCERTAIN",
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


def source_topology_detail(element, issue):
    identity = (
        f"entity={element.entity_key}, STEP={element.step_id}, GlobalId={element.global_id}, "
        f"IFC type={element.ifc_type}"
    )
    intersection = issue.get("self_intersection", {})
    reason = issue.get("reason")
    if reason == "SELF_INTERSECTION":
        return f"Source self-intersection confirmed: {identity}; witness={intersection.get('witness', {})}"
    if reason == "SELF_INTERSECTION_UNCERTAIN":
        return f"Source self-intersection could not be resolved: {identity}; evidence={intersection}"
    if reason == "SHELL_CONTACT":
        return f"Source shell contact requires verified union: {identity}; evidence={intersection}"
    if reason == "INVALID_SHELL_WINDING":
        return f"Invalid source shell winding: {identity}; witness={intersection.get('witness', {})}"
    return (
        f"Unsupported source geometry: {identity}; "
        f"source mesh quality={issue.get('mesh_quality', {})}; {element.mapping_rationale}"
    )


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
