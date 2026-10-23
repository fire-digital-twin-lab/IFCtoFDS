"""Bounded result projection shared by worker and HTTP delivery."""

from ifc_to_fds.modules.reference.api import research_context
from ifc_to_fds.modules.artifacts.contracts import ARTIFACTS

def public_result(result, *, research_reader=None):
    report = result["report"]

    def counts(value):
        if isinstance(value, dict):
            return {k: counts(v) for k, v in value.items()}
        if isinstance(value, list):
            return len(value)
        return value

    return dict(
        schema_version="0.5.0",
        status=result["status"],
        mapping_status=result["mapping_status"],
        simulation_status=result["simulation_status"],
        output_complete=result["output_complete"],
        source_filename=result["manifest"]["source_filename"],
        profile=result["configuration"].get("profile", "mapping"),
        coverage=counts(report["coverage"]),
        timings=result["timings"],
        gates={
            k: dict(
                status=v["status"], required=v["required"], reason=v["reason"][:1000]
            )
            for k, v in report["gates"].items()
        },
        findings=report["findings"][:20],
        findings_count=len(report["findings"]),
        blocker_count=sum(
            v["required"] and v["status"] not in ("PASS", "NOT_APPLICABLE")
            for v in report["gates"].values()
        ),
        research=(research_reader or research_context)(
            result["manifest"]["sources"], result["configuration"], report
        ),
        artifacts={k: dict(filename=v) for k, v in ARTIFACTS.items()},
    )
