import pytest

from ifc_to_fds.modules.fds.api import parse_fds
from ifc_to_fds.modules.verification.api import prepare_geometry_run
from tests.support.solver_cases import solver_cases


@pytest.mark.parametrize("name", ["obst", "geom", "hole", "vent", "multi_mesh"])
def test_cold_flow_changes_only_time_and_retains_geometry(name):
    original = solver_cases()[name]
    changed, evidence = prepare_geometry_run(original, 1.0)
    left, right = parse_fds(original), parse_fds(changed)
    assert [(r.kind, r.values, r.source) for r in left.records if r.kind != "TIME"] == [
        (r.kind, r.values, r.source) for r in right.records if r.kind != "TIME"
    ]
    assert evidence["geometry_changed"] is False
    assert evidence["source_sha256"] != evidence["derived_sha256"]
    assert evidence["changes"] == [
        {"namelist": "TIME", "field": "T_END", "before": 0, "after": 1}
    ]


@pytest.mark.parametrize("duration", [0, -1, float("inf"), float("nan"), True])
def test_invalid_cold_flow_duration_is_rejected(duration):
    with pytest.raises(ValueError, match="finite and positive"):
        prepare_geometry_run(solver_cases()["obst"], duration)


@pytest.mark.parametrize("mutation", ["running", "duplicate", "unknown_physics"])
def test_existing_scenario_is_never_silently_rewritten(mutation):
    text = solver_cases()["obst"]
    if mutation == "running":
        text = text.replace("T_END=0", "T_END=60")
    elif mutation == "duplicate":
        text = text.replace("&TIME", "&TIME T_END=0 /\n&TIME")
    else:
        text = text.replace("&TAIL", "&REAC FUEL='PROPANE' /\n&TAIL")
    with pytest.raises(ValueError):
        prepare_geometry_run(text)
