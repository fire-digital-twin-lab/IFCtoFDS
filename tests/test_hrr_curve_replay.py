"""Measured HRR curves are replayed point by point (plan M4.2) and FDS reproduces them (plan M4.5)."""

import csv
import os
import subprocess
from pathlib import Path

import pytest

from ifc_to_fds.domain.mapping import MappingPlan
from ifc_to_fds.fire.physics_assessment import assess_scenario_physics
from ifc_to_fds.fire.scenario_emitter import EVSelection, emit_fire_scenario
from ifc_to_fds.validation.parser import parse_fds

CURVE = [(0, 0), (20, 60), (40, 120), (80, 120), (100, 0)]  # s, kW; inside the e-bike preset range
SOURCE = "Synthetic replay curve for the solver check"


def vehicle(**changes):
    return dict(
        preset_id="e-bike-lfp", position=[1.0, 1.0, 0.4], geometry_mode="PARAMETRIC",
        dimensions=[1.0, 0.4, 0.6], floor_z_m=0.0, ground_clearance_m=0.1,
        hrr_curve_kw=CURVE, hrr_curve_source=SOURCE, **changes,
    )


@pytest.mark.parametrize("change, message", [
    (dict(hrr_curve_source=None), "one-line source"),
    (dict(hrr_curve_source="line one\n&TAIL /"), "one-line source"),
    (dict(hrr_curve_kw=[(5, 0), (20, 60)]), "start at t=0"),
    (dict(hrr_curve_kw=[(0, 0), (20, 60), (20, 80)]), "increase"),
    (dict(hrr_curve_kw=[(0, 0), (20, -1)]), "nonnegative"),
    (dict(peak_hrr_mw=0.5), "contradicts"),
])
def test_bad_curves_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        EVSelection.model_validate({**vehicle(), **change})


def test_curve_sets_the_peak_and_is_replayed_point_by_point():
    assert EVSelection.model_validate(vehicle()).peak_hrr_mw == pytest.approx(0.12)
    bundle = emit_fire_scenario(MappingPlan(), "a" * 64, [vehicle(ignition_delay_s=5)])
    ramp = [r for r in parse_fds(bundle.fds_fragment, require_core_namelists=False).records if r.kind == "RAMP"]
    points = [(r.values["T"][0], r.values["F"][0]) for r in ramp]
    assert points == [(0.0, 0.0)] + [(t + 5, q / 120) for t, q in CURVE]


def test_energy_of_the_replayed_curve_is_read_back_from_the_deck():
    bundle = emit_fire_scenario(MappingPlan(), "a" * 64, [vehicle()])
    text = "&HEAD CHID='e' /\n&TIME T_END=200 /\n&MESH IJK=20,20,15, XB=0,2,0,2,0,1.5 /\n" + bundle.fds_fragment + "\n&TAIL /"
    expected_mj = sum((t2 - t1) * (q1 + q2) / 2 for (t1, q1), (t2, q2) in zip(CURVE, CURVE[1:])) / 1000
    assert assess_scenario_physics(text, bundle, None)["nominal_energy_mj"] == pytest.approx(expected_mj, rel=1e-6)


@pytest.mark.solver
def test_fds_heat_release_follows_the_replayed_curve(tmp_path):
    bundle = emit_fire_scenario(MappingPlan(), "a" * 64, [vehicle()])
    deck = "\n".join([
        "&HEAD CHID='replay' /", "&MESH IJK=20,20,15, XB=0,2,0,2,0,1.5 /", "&TIME T_END=110 /",
        "&DUMP DT_HRR=1. /",
        *[f"&VENT MB='{side}', SURF_ID='OPEN' /" for side in ("XMIN", "XMAX", "YMIN", "YMAX", "ZMAX")],
        bundle.fds_fragment, "&TAIL /", "",
    ])
    exe = Path(os.environ["IFCFDS_SOLVER"])
    env = {**os.environ, "PATH": os.pathsep.join([str(exe.parent / "mpi"), str(exe.parent), os.environ["PATH"]])}
    (tmp_path / "replay.fds").write_text(deck)
    run = subprocess.run([str(exe), "replay.fds"], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=900)
    assert "completed successfully" in run.stdout + run.stderr, (run.stdout + run.stderr)[-800:]
    rows = list(csv.reader((tmp_path / "replay_hrr.csv").open()))
    hrr = {round(float(r[0])): float(r[rows[1].index("HRR")]) for r in rows[2:]}
    # FDS reports the instantaneous LES heat release: it fluctuates by about +/-10% and lags the fuel supply
    # by about one second (measured 2026-11-15), so single samples are not compared. What must match is the
    # energy, the steady peak and the timing of the curve.
    released_mj = sum((hrr[t] + hrr[t + 1]) / 2 for t in range(0, 108)) / 1000
    assert released_mj == pytest.approx(8.4, rel=0.01)
    plateau = sum(hrr[t] for t in range(45, 81)) / 36
    assert plateau == pytest.approx(120, rel=0.05)
    half_peak_at = next(t for t in sorted(hrr) if hrr[t] >= 60)
    assert 20 <= half_peak_at <= 23, half_peak_at  # the curve reaches 60 kW at 20 s
