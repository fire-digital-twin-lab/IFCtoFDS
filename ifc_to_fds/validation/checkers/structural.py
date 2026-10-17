"""Account for structural solids before reporting a complete enclosure mapping."""

from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation.model import GateResult, GateStatus

STRUCTURAL_TYPES = {
    "IFCWALL",
    "IFCWALLSTANDARDCASE",
    "IFCCURTAINWALL",
    "IFCSLAB",
    "IFCCOLUMN",
    "IFCBEAM",
    "IFCROOF",
}


class StructuralCompletenessChecker:
    name = "structural_completeness"

    def check(self, context):
        emitted = {
            p.source.get("entity_key")
            for p in context.parsed.primitives
            if p.kind in ("OBST", "GEOM")
        }
        expected, missing, withheld, disposed = [], [], [], []
        for e in context.model.elements:
            if (
                e.ifc_type.upper() not in STRUCTURAL_TYPES
                or e.role != "PHYSICAL"
                or e.scope_decision == "OUT_OF_SCOPE"
            ):
                continue
            expected.append(e.entity_key)
            if e.mapping_strategy == "EXCLUDED_APPROVED" or (
                e.simulation_role == "REFERENCE_GEOMETRY" and e.decision
            ):
                disposed.append(e.entity_key)
            elif e.mapping_strategy in ("GEOM", "OBST"):
                if e.entity_key not in emitted:
                    missing.append(e.entity_key)
            else:
                withheld.append(e.entity_key)
        return CheckerOutcome(
            gate_name=self.name,
            result=GateResult(
                status=GateStatus.FAIL
                if missing
                else GateStatus.INCONCLUSIVE
                if withheld
                else GateStatus.PASS,
                reason=f"{len(expected)} structural entities; {len(missing)} missing required solids; {len(withheld)} withheld/unresolved; {len(disposed)} reviewed dispositions. This checks mapping completeness, not source-building airtightness.",
                evidence={
                    "missing": missing,
                    "withheld": withheld,
                    "reviewed_dispositions": disposed,
                },
            ),
            findings=[],
            metrics={
                "structural_completeness": {
                    "source_count": len(expected),
                    "missing": missing,
                    "withheld": withheld,
                }
            },
        )
