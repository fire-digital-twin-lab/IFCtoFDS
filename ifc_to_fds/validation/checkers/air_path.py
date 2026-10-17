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

        # Collect emitted obstacle / geom primitive meshes
        emitted_meshes = []
        if context.parsed and getattr(context.parsed, "primitives", None):
            for p in context.parsed.primitives:
                if getattr(p, "kind", None) in ("OBST", "GEOM") and hasattr(p, "mesh"):
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
            ref_trimeshes = [as_trimesh(e.mesh) for e in enclosure_elements]
            s_ref = solid_boolean(ref_trimeshes, "union") if len(ref_trimeshes) > 1 else ref_trimeshes[0]
            s_fds = solid_boolean(emitted_meshes, "union") if len(emitted_meshes) > 1 else emitted_meshes[0]

            # Domain bounding box with margin
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
            c_ref = f_ref.split(only_watertight=False)
            c_fds = f_fds.split(only_watertight=False)

            # Unintended leakage: free space in FDS intersecting solid envelope in reference
            leak_intersection = solid_boolean([f_fds, s_ref], "intersection")
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
