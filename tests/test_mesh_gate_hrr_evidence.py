"""ARCH-01: the mesh gate takes peak-HRR evidence from the selection; only fire code opens the EV preset library."""

import pytest

from ifc_to_fds.domain.validation.model import GateStatus
from ifc_to_fds.fire import EVSelection
from ifc_to_fds.fire.mesh_metrics import ev_peak_hrr_evidence
from ifc_to_fds.validation.checkers.mesh_resolution import check_mesh_resolution


@pytest.fixture
def empty_library(monkeypatch, tmp_path):
    monkeypatch.setenv("IFCFDS_EV_LIBRARY_DIR", str(tmp_path / "missing"))


def test_a_stated_peak_hrr_needs_no_library(empty_library):
    res = check_mesh_resolution({"ev_selections": [{"id": "v", "peak_hrr_kw": 5000.0}]}, cell_size=0.2)
    assert res.status == GateStatus.INCONCLUSIVE
    item = res.evidence["ev_evaluations"][0]
    assert item["peak_hrr_basis"] == "EXPLICIT_SELECTION" and item["peak_hrr_kw"] == 5000.0


def test_a_bare_preset_is_inconclusive_not_a_loader_error_and_not_no_fire(empty_library):
    res = check_mesh_resolution({"ev_selections": [{"preset_id": "auto-nmc"}]}, cell_size=0.2)
    assert res.status == GateStatus.INCONCLUSIVE and "not resolved" in res.reason
    assert res.evidence["preset_id"] == "auto-nmc"


def test_an_ev_selection_keeps_the_preset_evidence_it_always_reported():
    ev = EVSelection(preset_id="auto-nmc", position=(0.0, 0.0, 0.75))
    expected = ev_peak_hrr_evidence(ev)
    item = check_mesh_resolution({"ev_selections": [ev]}, cell_size=0.2).evidence["ev_evaluations"][0]
    assert expected["peak_hrr_basis"] == "PRESET_RANGE_MIDPOINT_ASSUMPTION"
    assert {k: item[k] for k in expected} == expected  # basis, range, preset id, confidence, citations
    assert ev.peak_hrr_evidence() == expected


def test_an_ev_selection_still_reports_a_missing_preset_as_before(empty_library):
    with pytest.raises(ValueError, match="Unknown EV preset"):
        check_mesh_resolution({"ev_selections": [EVSelection(preset_id="auto-nmc", position=(0, 0, 0.75))]}, cell_size=0.2)
