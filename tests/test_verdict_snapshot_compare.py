"""verdict-snapshot --compare accepts the count-only baselines kept for the real buildings (roadmap A4.12)."""

import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location("verdict_snapshot", Path(__file__).parents[1] / "scripts" / "verdict-snapshot.py")
verdict_snapshot = importlib.util.module_from_spec(spec)
# The script switches solver auto-discovery off at import. Collecting this module must not leak that into the
# solver tests of the same session (a leak made `pytest -m solver` fail test_p4c2_executes_three_pinned_fds_cases).
_autodiscovery = os.environ.get("IFCFDS_SOLVER_AUTODISCOVERY")
try:
    spec.loader.exec_module(verdict_snapshot)
finally:
    if _autodiscovery is None:
        os.environ.pop("IFCFDS_SOLVER_AUTODISCOVERY", None)
    else:
        os.environ["IFCFDS_SOLVER_AUTODISCOVERY"] = _autodiscovery

OLD = {"status": "MAPPING_VERIFIED", "elements": {"MATCHED": 2, "SEMANTIC_ONLY": 1}, "findings": {}, "timings": {"wall_s": 9}}
NEW = {"status": "MAPPING_VERIFIED", "element_statuses": {"a": "MATCHED", "b": "MATCHED", "c": "SEMANTIC_ONLY"},
       "findings_by_gate": {}, "wall_s": 12}


def test_matching_counts_are_no_difference(capsys):
    assert verdict_snapshot.compare(OLD, NEW) == 0
    assert "differences: 0" in capsys.readouterr().out


def test_a_changed_count_status_or_finding_is_reported(capsys):
    changed = dict(NEW, element_statuses={"a": "MATCHED", "b": "DEVIATED", "c": "SEMANTIC_ONLY"}, status="REJECTED",
                   findings_by_gate={"geometry": 1})
    assert verdict_snapshot.compare(OLD, changed) == 1
    out = capsys.readouterr().out
    assert "status: MAPPING_VERIFIED -> REJECTED" in out and "elements[DEVIATED]: 0 -> 1" in out
    assert "elements[MATCHED]: 2 -> 1" in out and "findings[geometry]: 0 -> 1" in out
