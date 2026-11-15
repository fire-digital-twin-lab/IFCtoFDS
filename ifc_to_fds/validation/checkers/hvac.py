"""Compare operational records from disk text with independently rebuilt intent."""

import math

from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.domain.validation import Finding, GateResult, GateStatus, Severity
from ifc_to_fds.mep.network import build_hvac_network
from ifc_to_fds.mep.fds_records import network_records


def friction_findings(plan):
    """FDS 6.11.1 friction pitfalls, measured against the pinned solver (tests/test_hvac_fds_pressure.py)."""
    smooth = [d.id for d in plan.ducts if d.spec.roughness_m == 0]
    noncircular = [
        d.id for d in plan.ducts
        if d.spec.diameter_m is None and d.spec.perimeter_m ** 2 > 4 * math.pi * d.spec.area_m2 * (1 + 1e-3)
    ]
    notes = [
        ("HVAC-FRICTION-0001", smooth, "HVAC duct has ROUGHNESS=0",
         "FDS applies no wall friction when ROUGHNESS is 0, so these ducts are frictionless rather than smooth-pipe."),
        ("HVAC-FRICTION-0002", noncircular, "Non-circular HVAC duct friction uses the equivalent round diameter",
         "FDS takes D = sqrt(4A/pi) from AREA and ignores PERIMETER for friction; a 0.5 x 0.3 m duct then has about 18% "
         "less friction pressure drop than with the hydraulic diameter 4A/P. Review the loss budget."),
    ]
    return [
        Finding(id=ident, severity=Severity.P2, category="hvac", title=f"{title}: {len(ids)} duct(s)",
                detail=f"{why} Ducts: {', '.join(sorted(ids)[:5])}{' ...' if len(ids) > 5 else ''}",
                verification_level="simulation")
        for ident, ids, title, why in notes if ids
    ]


class HvacNetworkChecker:
    name = "hvac"

    def check(self, context):
        if context.parsed is None or context.model is None:
            return CheckerOutcome(self.name, GateResult(status=GateStatus.INCONCLUSIVE, reason="FDS text/source missing"))
        try:
            plan = build_hvac_network(context.model)
            expected = {(kind, tuple(values.get("TYPE_ID", [])), values["ID"][0]): (values, keys)
                        for kind, values, keys in network_records(plan)}
            actual = {(r.kind, tuple(r.values.get("TYPE_ID", [])), r.id): r
                      for r in context.parsed.operational_records}
            if set(expected) != set(actual):
                raise ValueError("Serialized HVAC record set differs from reviewed source network")
            for identity, (values, keys) in expected.items():
                r = actual[identity]
                if r.values != values or sorted(r.source.get("entity_keys", [])) != sorted(keys):
                    raise ValueError(f"HVAC parameters, topology or provenance changed: {identity}")
            if context.manifest:
                expected_assignments = plan.assignments()
                for record in context.manifest.records:
                    if record.entity_key in expected_assignments and sorted(record.fds_primitive_ids) != sorted(expected_assignments[record.entity_key]):
                        raise ValueError(f"Manifest HVAC assignments changed: {record.entity_key}")
            findings = friction_findings(plan)
            return CheckerOutcome(self.name, GateResult(
                status=GateStatus.PASS if expected else GateStatus.NOT_APPLICABLE,
                reason="Operational HVAC network independently reconstructed" if expected else "No operational HVAC network requested",
            ), findings, metrics={"hvac_nodes": len(plan.nodes), "hvac_ducts": len(plan.ducts), "hvac_friction_findings": len(findings)})
        except (ValueError, KeyError, TypeError) as exc:
            finding = Finding(id="HVAC-001", severity=Severity.P1, category=self.name,
                              title="HVAC network differs from source intent", detail=str(exc))
            return CheckerOutcome(self.name, GateResult(status=GateStatus.FAIL, reason=str(exc)), [finding])
