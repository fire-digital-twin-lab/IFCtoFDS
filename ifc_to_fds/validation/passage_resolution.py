"""Passage resolution gate: can the chosen FDS grid keep every opening open and every enclosure solid?

Everything here is a prediction from the serialized MESH and OBST records, made before the solver runs. It
names the element and proposes the largest cell size that removes the problem. The solver's own SMV output
is read later by the effective-geometry gate.
"""

import math

from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import Finding, GateResult, GateStatus, Severity
from .effective import check_opening_grid_alignment

ENCLOSURE_TYPES = {
    "IFCWALL",
    "IFCWALLSTANDARDCASE",
    "IFCCURTAINWALL",
    "IFCSLAB",
    "IFCROOF",
}

MIN_CELLS_ACROSS_PASSAGE = 2


def _round_down_mm(value):
    return math.floor(value * 1000 + 1e-9) / 1000


def _collapsed_axes(xb, mesh):
    """Axes on which both faces of the box snap to the same grid plane of this mesh."""
    domain, ijk = mesh.values["XB"], mesh.values["IJK"]
    if any(min(xb[2 * a + 1], domain[2 * a + 1]) <= max(xb[2 * a], domain[2 * a]) for a in range(3)):
        return []
    out = []
    for axis in range(3):
        step = (domain[2 * axis + 1] - domain[2 * axis]) / ijk[axis]
        low = math.floor((xb[2 * axis] - domain[2 * axis]) / step + 0.5)
        high = math.floor((xb[2 * axis + 1] - domain[2 * axis]) / step + 0.5)
        if low == high:
            out.append((axis, xb[2 * axis + 1] - xb[2 * axis], step))
    return out


class PassageResolutionChecker:
    name = "passage_resolution"

    def check(self, context, parsed=None) -> CheckerOutcome:
        parsed = parsed if parsed is not None else context.parsed_fds
        model = context.model
        if parsed is None or model is None:
            return CheckerOutcome(
                gate_name=self.name,
                result=GateResult(status=GateStatus.INCONCLUSIVE, reason="FDS text or model missing"),
                findings=[],
            )
        elements = {e.entity_key: e for e in model.elements}
        findings, assessed, not_estimated = [], 0, 0

        def report(element_key, title, detail):
            findings.append(
                Finding(
                    id=f"FND-RES-{len(findings) + 1:04}",
                    severity=Severity.P1,
                    category=self.name,
                    title=title,
                    detail=detail,
                    element_id=element_key,
                    verification_level="simulation",
                )
            )

        for e in model.elements:
            for opening in getattr(e, "openings", []):
                if not getattr(opening, "mesh", None) or getattr(e, "bounding_box", None) is None:
                    not_estimated += 1
                    continue
                grid = check_opening_grid_alignment(opening.mesh, e.bounding_box, parsed)
                if grid["status"] != "ESTIMATED":
                    not_estimated += 1
                    continue
                assessed += 1
                if grid["risk_sealed_by_grid"]:
                    span = min(grid["clear_spans_m"])
                    report(
                        e.entity_key,
                        f"Opening narrower than {MIN_CELLS_ACROSS_PASSAGE} cells: {e.global_id}",
                        f"Opening {opening.opening_global_id} in {e.ifc_type} {e.global_id} has a clear span of "
                        f"{span:.3f} m on cells of {max(grid['mesh_spacing_m']):.3f} m and may be sealed by the grid. "
                        f"Use cells of at most {_round_down_mm(span / MIN_CELLS_ACROSS_PASSAGE):.3f} m.",
                    )

        meshes = [r for r in parsed.records if r.kind == "MESH"]
        for primitive in parsed.primitives:
            key = (getattr(primitive, "source", None) or {}).get("entity_key")
            element = elements.get(key)
            if primitive.kind != "OBST" or element is None or element.ifc_type.upper() not in ENCLOSURE_TYPES:
                continue
            xb = primitive.values.get("XB", [])
            if len(xb) != 6:
                continue
            assessed += 1
            for mesh in meshes:
                for axis, thickness, step in _collapsed_axes(xb, mesh):
                    report(
                        key,
                        f"Thin solid collapses on the grid: {element.global_id}",
                        f"{primitive.id} ({element.ifc_type} {element.global_id}) is {thickness:.3f} m thick on "
                        f"{'XYZ'[axis]} but both faces snap to one plane of the {step:.3f} m grid. "
                        f"Use cells of at most {_round_down_mm(thickness):.3f} m.",
                    )
                    break

        metrics = {"passage_resolution": {"assessed": assessed, "openings_not_estimated": not_estimated}}
        if findings:
            return CheckerOutcome(
                gate_name=self.name,
                result=GateResult(
                    status=GateStatus.FAIL,
                    reason=f"{len(findings)} passage(s) or solid(s) are not resolved by the grid: "
                    + "; ".join(f.title for f in findings[:3]),
                    evidence=metrics["passage_resolution"],
                ),
                findings=findings,
                metrics=metrics,
            )
        if not assessed:
            status = GateStatus.INCONCLUSIVE if not_estimated else GateStatus.NOT_APPLICABLE
            reason = (
                f"{not_estimated} opening(s) are not axis-aligned boxes; their resolution was not estimated"
                if not_estimated
                else "No openings or enclosure obstructions to assess"
            )
            return CheckerOutcome(gate_name=self.name, result=GateResult(status=status, reason=reason), findings=[], metrics=metrics)
        return CheckerOutcome(
            gate_name=self.name,
            result=GateResult(
                status=GateStatus.PASS,
                reason=f"{assessed} openings and enclosure solids resolved on the grid; {not_estimated} opening(s) not estimable",
                evidence=metrics["passage_resolution"],
            ),
            findings=[],
            metrics=metrics,
        )
