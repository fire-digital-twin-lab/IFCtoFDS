"""Air-path and enclosure topology checker.

Verifies airtightness of compartment boundaries and detects unintended air leaks
by comparing free-space connected components and leakage volume using binary64 Manifold CSG.
"""

from typing import List

from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, Severity
from ifc_to_fds.geometry.boolean import solid_boolean
from ifc_to_fds.geometry.mesh import as_trimesh, box_mesh, valid_solid


ENCLOSURE_TYPES = {
    "IFCWALL",
    "IFCWALLSTANDARDCASE",
    "IFCCURTAINWALL",
    "IFCSLAB",
    "IFCROOF",
}


class AirPathTopologyChecker:
    name = "air_path"

    def check(self, context) -> CheckerOutcome:
        elements = getattr(context.model, "elements", [])
        enclosure_elements = [
            e
            for e in elements
            if e.ifc_type.upper() in ENCLOSURE_TYPES
            and getattr(e, "role", "PHYSICAL") == "PHYSICAL"
            and getattr(e, "scope_decision", "") in ("IN_SCOPE", "BOUNDARY_RETAINED")
            and getattr(e, "mapping_strategy", "") in ("OBST", "GEOM")
            and getattr(e, "mesh", None)
            and valid_solid(e.mesh)
        ]

        if not enclosure_elements:
            return CheckerOutcome(
                gate_name=self.name,
                result=GateResult(
                    status=GateStatus.NOT_APPLICABLE,
                    reason="No in-scope structural enclosure elements present for air-path analysis.",
                ),
                findings=[],
                metrics={"air_path": {"enclosure_elements_count": 0}},
            )

        # Collect emitted obstacle / geom primitive meshes originating from enclosure elements
        enclosure_keys = {e.entity_key for e in enclosure_elements}
        known_elements = {e.entity_key: e for e in elements} if elements else {}
        emitted_meshes = []
        if context.parsed and getattr(context.parsed, "primitives", None):
            for p in context.parsed.primitives:
                if getattr(p, "kind", None) in ("OBST", "GEOM") and hasattr(p, "mesh"):
                    source_key = p.source.get("entity_key") if getattr(p, "source", None) else None
                    if source_key:
                        src_elem = known_elements.get(source_key)
                        if src_elem:
                            if src_elem.entity_key not in enclosure_keys:
                                continue  # Exclude non-enclosure obstacles (MEP, columns, equipment)
                        elif source_key not in enclosure_keys:
                            continue
                    try:
                        m = p.mesh()
                        if m and valid_solid(m):
                            emitted_meshes.append(as_trimesh(m))
                    except Exception:
                        pass

        if not emitted_meshes:
            return CheckerOutcome(
                gate_name=self.name,
                result=GateResult(
                    status=GateStatus.FAIL,
                    reason=f"{len(enclosure_elements)} enclosure solids expected, but zero valid FDS obstruction/geometry primitives emitted.",
                ),
                findings=[
                    Finding(
                        id="FND-AIR-0001",
                        severity=Severity.P1,
                        category=self.name,
                        title="Enclosure uncontained: zero FDS geometry emitted",
                        detail=f"{len(enclosure_elements)} structural enclosure elements present in source model, but no valid FDS obstacle primitives were emitted.",
                        element_id=enclosure_elements[0].entity_key,
                    )
                ],
                metrics={"air_path": {"enclosure_elements_count": len(enclosure_elements), "emitted_count": 0}},
            )

        try:
            # Build unified reference envelope solid
            from ifc_to_fds.mapping.boundary import target_mesh

            ref_trimeshes = []
            for e in enclosure_elements:
                m = target_mesh(e) if getattr(e, "boundary_policy", None) else e.mesh
                if m and valid_solid(m):
                    ref_trimeshes.append(as_trimesh(m))
            if not ref_trimeshes:
                ref_trimeshes = [as_trimesh(e.mesh) for e in enclosure_elements]

            s_ref = solid_boolean(ref_trimeshes, "union") if len(ref_trimeshes) > 1 else ref_trimeshes[0]
            s_fds = solid_boolean(emitted_meshes, "union") if len(emitted_meshes) > 1 else emitted_meshes[0]

            if s_ref is None or s_fds is None or not hasattr(s_ref, "bounds") or not hasattr(s_fds, "bounds"):
                return CheckerOutcome(
                    gate_name=self.name,
                    result=GateResult(
                        status=GateStatus.INCONCLUSIVE,
                        reason="Unable to construct valid boundary manifold for reference or emitted enclosure geometry.",
                    ),
                    findings=[],
                    metrics={"air_path": {"enclosure_elements_count": len(enclosure_elements)}},
                )

            # Domain bounding box: constrain to explicit simulation domain when defined
            sim_domain = getattr(context.model, "simulation_domain", None)
            if sim_domain:
                m_domain = as_trimesh(box_mesh(sim_domain))
                try:
                    s_ref_clipped = solid_boolean([s_ref, m_domain], "intersection")
                    if s_ref_clipped and hasattr(s_ref_clipped, "volume") and s_ref_clipped.volume > 0:
                        s_ref = s_ref_clipped
                except Exception:
                    pass
            else:
                b = s_ref.bounds
                margin = 0.5
                domain_bbox = BoundingBox(
                    xmin=float(b[0][0] - margin),
                    xmax=float(b[1][0] + margin),
                    ymin=float(b[0][1] - margin),
                    ymax=float(b[1][1] + margin),
                    zmin=float(b[0][2] - margin),
                    zmax=float(b[1][2] + margin),
                )
                m_domain = as_trimesh(box_mesh(domain_bbox))

            # Free space subtraction
            f_ref = solid_boolean([m_domain, s_ref], "difference")
            f_fds = solid_boolean([m_domain, s_fds], "difference")

            # Topological connected components of free space
            c_ref = f_ref.split(only_watertight=False) if getattr(f_ref, "is_volume", False) and f_ref.volume > 0 else []
            c_fds = f_fds.split(only_watertight=False) if getattr(f_fds, "is_volume", False) and f_fds.volume > 0 else []

            # Unintended leakage: free space in FDS intersecting solid envelope in reference
            if getattr(f_fds, "is_volume", False) and f_fds.volume > 0 and getattr(s_ref, "is_volume", False) and s_ref.volume > 0:
                leak_intersection = solid_boolean([f_fds, s_ref], "intersection")
            else:
                leak_intersection = None

            # Subtract intentional openings from leak intersection if present
            opening_trimeshes = []
            for e in enclosure_elements:
                for op in getattr(e, "openings", []):
                    if getattr(op, "mesh", None) and valid_solid(op.mesh):
                        opening_trimeshes.append(as_trimesh(op.mesh))
                    elif getattr(op, "bounding_box", None):
                        opening_trimeshes.append(as_trimesh(box_mesh(op.bounding_box)))
            if opening_trimeshes and leak_intersection and hasattr(leak_intersection, "volume") and leak_intersection.volume > 0:
                try:
                    u_openings = solid_boolean(opening_trimeshes, "union") if len(opening_trimeshes) > 1 else opening_trimeshes[0]
                    leak_sub = solid_boolean([leak_intersection, u_openings], "difference")
                    if leak_sub is not None:
                        leak_intersection = leak_sub
                except Exception:
                    pass

            v_leak = float(leak_intersection.volume) if leak_intersection and hasattr(leak_intersection, "volume") else 0.0

            surface_tol = getattr(context.config, "surface_tolerance_m", 0.001) if context.config else 0.001
            v_ref = float(s_ref.volume)
            leak_ratio = v_leak / max(v_ref, 1e-12)
            leak_tol = max(1e-4, (surface_tol ** 3) / max(v_ref, 1e-12))

            findings: List[Finding] = []
            status = GateStatus.PASS
            reasons = []

            if leak_ratio > leak_tol:
                status = GateStatus.FAIL
                reasons.append(f"Unintended envelope leak volume: {v_leak:.6f} m3 ({leak_ratio*100:.3f}% of envelope)")
                findings.append(
                    Finding(
                        id=f"FND-AIR-{len(findings)+1:04}",
                        severity=Severity.P1,
                        category=self.name,
                        title=f"Unintended envelope air leak: {v_leak:.6f} m3",
                        detail=f"Emitted FDS obstacles exhibit an unintended leak volume of {v_leak:.6f} m3 penetrating the source building envelope.",
                        element_id=enclosure_elements[0].entity_key,
                    )
                )

            if len(c_fds) < len(c_ref):
                status = GateStatus.FAIL
                reasons.append(f"Compartmentation breach: free space components collapsed from {len(c_ref)} in source to {len(c_fds)} in FDS")
                findings.append(
                    Finding(
                        id=f"FND-AIR-{len(findings)+1:04}",
                        severity=Severity.P1,
                        category=self.name,
                        title="Compartmentation breached: cavities merged",
                        detail=f"Free-space topology changed: {len(c_ref)} isolated cavities in source envelope merged into {len(c_fds)} cavities in FDS.",
                        element_id=enclosure_elements[0].entity_key,
                    )
                )
            elif len(c_fds) > len(c_ref):
                status = GateStatus.FAIL
                reasons.append(f"Compartmentation segmented: free space components increased from {len(c_ref)} in source to {len(c_fds)} in FDS (unintended internal blockage)")
                findings.append(
                    Finding(
                        id=f"FND-AIR-{len(findings)+1:04}",
                        severity=Severity.P2,
                        category=self.name,
                        title="Compartmentation altered: cavities segmented",
                        detail=f"Free-space topology changed: {len(c_ref)} isolated cavities in source envelope partitioned into {len(c_fds)} cavities in FDS by unexpected obstacle geometry.",
                        element_id=enclosure_elements[0].entity_key,
                    )
                )

            reason_str = "; ".join(reasons) if reasons else f"Enclosure topology verified: {len(c_ref)} cavities preserved, leak ratio {leak_ratio:.6e} within tolerance."
            return CheckerOutcome(
                gate_name=self.name,
                result=GateResult(
                    status=status,
                    reason=reason_str,
                    evidence={
                        "enclosure_count": len(enclosure_elements),
                        "leak_volume_m3": v_leak,
                        "leak_ratio": leak_ratio,
                        "source_cavities": len(c_ref),
                        "fds_cavities": len(c_fds),
                    },
                ),
                findings=findings,
                metrics={
                    "air_path": {
                        "enclosure_count": len(enclosure_elements),
                        "leak_volume_m3": v_leak,
                        "leak_ratio": leak_ratio,
                    }
                },
            )
        except Exception as exc:
            return CheckerOutcome(
                gate_name=self.name,
                result=GateResult(
                    status=GateStatus.INCONCLUSIVE,
                    reason=f"Air-path topology check inconclusive: {exc}",
                ),
                findings=[],
                metrics={"air_path": {"error": str(exc)}},
            )
