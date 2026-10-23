"""Compare serialized static geometry before/after an external editor export.

This gate does not attest that PyroSim was launched or validate fire physics.
Renamed IDs need an explicit bijection and independent full-solid proof.
"""

import hashlib

from ifc_to_fds.domain.validation import AuditConfig, GateResult, GateStatus
from ifc_to_fds.modules.fds.api import parse_fds
from ifc_to_fds.modules.geometry.api import compare_solids, metrics_pass


def compare_roundtrip_geometry(original_text, exported_text, config=None, aliases=None):
    config = config or AuditConfig()
    aliases = {} if aliases is None else aliases
    original, exported = parse_fds(original_text), parse_fds(exported_text)
    evidence = {
        "scope": "STATIC_GEOMETRY_ONLY",
        "original_sha256": hashlib.sha256(original_text.encode()).hexdigest(),
        "exported_sha256": hashlib.sha256(exported_text.encode()).hexdigest(),
        "tolerances": config.model_dump(
            include={
                "surface_tolerance_m",
                "relative_volume_tolerance",
                "min_solid_iou",
            }
        ),
        "aliases": aliases,
        "comparisons": {},
    }

    def result(status, reason):
        return GateResult(status=status, reason=reason, evidence=evidence)

    if original.errors or exported.errors:
        return result(
            GateStatus.FAIL,
            f"FDS parse errors: source={original.errors}; exported={exported.errors}",
        )
    if original.unsupported or exported.unsupported:
        return result(
            GateStatus.INCONCLUSIVE, "Round-trip syntax exceeds the supported subset"
        )
    left = {r.id: r for r in original.primitives}
    right = {r.id: r for r in exported.primitives}
    if (
        not any(r.kind in ("OBST", "GEOM") for r in left.values())
        or "" in left
        or "" in right
    ):
        return result(
            GateStatus.INCONCLUSIVE,
            "Static geometry and unambiguous primitive IDs are required",
        )
    if not isinstance(aliases, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in aliases.items()
    ):
        return result(GateStatus.FAIL, "Alias mapping must contain string IDs")
    if set(aliases) - left.keys() or len(set(aliases.values())) != len(aliases):
        return result(GateStatus.FAIL, "Alias mapping must be a source-ID bijection")
    targets = {pid: aliases.get(pid, pid) for pid in left}
    if len(set(targets.values())) != len(targets) or set(targets.values()) != set(
        right
    ):
        return result(
            GateStatus.FAIL, "Round-trip primitive inventory/identity differs"
        )

    def mesh_values(parsed):
        return [
            (r.values.get("IJK"), r.values.get("XB"))
            for r in parsed.records
            if r.kind == "MESH"
        ]

    if mesh_values(original) != mesh_values(exported):
        return result(GateStatus.FAIL, "Round-trip computational meshes differ")

    def surfaces(parsed):
        return {r.id: r.values for r in parsed.records if r.kind == "SURF"}

    if surfaces(original) != surfaces(exported):
        return result(GateStatus.FAIL, "Round-trip surface definitions differ")
    has_holes = any(r.kind == "HOLE" for r in original.primitives)
    for pid, target in targets.items():
        before, after = left[pid], right[target]
        if (
            has_holes
            or before.kind in ("HOLE", "VENT")
            or after.kind in ("HOLE", "VENT")
        ) and before.kind != after.kind:
            return result(
                GateStatus.FAIL, f"Round-trip primitive semantics changed: {pid}"
            )
        if before.values.get("SURF_ID") != after.values.get("SURF_ID"):
            return result(
                GateStatus.FAIL, f"Round-trip surface assignment changed: {pid}"
            )
        if any(
            r.kind == "GEOM" and len(r.values.get("SURF_ID", [])) > 1
            for r in (before, after)
        ):
            if before.values.get("VERTS") != after.values.get(
                "VERTS"
            ) or before.values.get("FACES") != after.values.get("FACES"):
                return result(
                    GateStatus.INCONCLUSIVE,
                    f"Per-face surface correspondence not proved: {pid}",
                )
        if before.kind in ("HOLE", "VENT"):
            # Exact equality of the supported operators. This is not proof of
            # the solver's cut-cell geometry or a general opening approximation.
            a = {k: v for k, v in before.values.items() if k != "ID"}
            b = {k: v for k, v in after.values.items() if k != "ID"}
            if a != b:
                return result(
                    GateStatus.FAIL, f"Round-trip opening/boundary changed: {pid}"
                )
            if before.kind == "VENT":
                xb = a.get("XB", [])
                if (
                    len(xb) != 6
                    or sum(xb[i] == xb[i + 1] for i in (0, 2, 4)) != 1
                    or any(xb[i] > xb[i + 1] for i in (0, 2, 4))
                ):
                    return result(GateStatus.FAIL, f"Invalid planar VENT: {pid}")
            evidence["comparisons"][pid] = {
                "proof": "EXACT_STATIC_OPERATOR",
                "kind": before.kind,
            }
            continue
        try:
            measured = compare_solids(left[pid].mesh(), [right[target].mesh()])
            evidence["comparisons"][pid] = measured
            if not metrics_pass(measured, config):
                return result(GateStatus.FAIL, f"Round-trip geometry changed: {pid}")
            if not measured["surface_proven"]:
                return result(
                    GateStatus.INCONCLUSIVE, f"Full surface proof unavailable: {pid}"
                )
        except ValueError as exc:
            return result(GateStatus.FAIL, f"Invalid round-trip solid {pid}: {exc}")
        except RuntimeError as exc:
            return result(
                GateStatus.INCONCLUSIVE, f"Unproved round-trip solid {pid}: {exc}"
            )
    return result(
        GateStatus.PASS,
        "Static solids, supported opening/boundary operators and surfaces preserved; editor execution, effective geometry and physics are separate",
    )
