"""Đối chiếu thể tích khí và diện tích mặt của GEOM với nghiệm giải tích."""

from hashlib import sha256
from pathlib import Path

import pytest

from ifc_to_fds.validation.acceptance import AuditConfig, GateResult
from ifc_to_fds.validation import effective_cutcell


DECK = (
    "&HEAD CHID='cutcell_volume' /\n"
    "&TIME T_END=0.02, DT=0.01 /\n"
    "&MESH ID='room', IJK=10,10,10, XB=0,1,0,1,0,1 /\n"
    "&GEOM ID='tet', VERTS=0.25,0.25,0.25,0.55,0.25,0.25,0.25,0.55,0.25,0.25,0.25,0.55, "
    "FACES=1,3,2,0,1,2,4,0,2,3,4,0,3,1,4,0 /\n&TAIL /\n"
)
PROBES = [
    dict(id="global_gas", bounds_m=(0, 1, 0, 1, 0, 1),
         expected=1 - 0.3**3 / 6, tolerance=1e-7, units="m3"),
    dict(id="corner_gas", bounds_m=(0.2, 0.3, 0.2, 0.3, 0.2, 0.3),
         expected=0.1**3 - 0.05**3, tolerance=1e-9, units="m3"),
    dict(id="face_gas", bounds_m=(0.3, 0.3, 0.2, 0.3, 0.2, 0.3),
         expected=0.1**2 - 0.05**2, tolerance=1e-8, units="m2"),
]


def test_cutcell_evidence_refuses_misaligned_probe_and_unsealed_csv(tmp_path, monkeypatch):
    bad = [PROBES[0], PROBES[1], {**PROBES[2], "bounds_m": (0.31, 0.31, 0.2, 0.3, 0.2, 0.3)}]
    result = effective_cutcell.certify_cutcell_geometry(DECK, bad, AuditConfig())
    assert result.status == "INCONCLUSIVE" and "mesh nodes" in result.reason
    (tmp_path / "cutcell_volume_devc.csv").write_text(
        "s,m3,m3,m2\nTime,global_gas,corner_gas,face_gas\n0,0.9955,0.000875,0.0075\n",
        encoding="utf-8",
    )

    def simulated_run(text, _config):
        return GateResult(status="PASS", evidence={
            "fds_sha256": sha256(text.encode()).hexdigest(),
            "reported_versions": ["6.11.1"], "sha256": "a" * 64,
            "directory": str(tmp_path), "files": {"cutcell_volume_devc.csv": "b" * 64},
        }), GateResult()

    monkeypatch.setattr(effective_cutcell, "solver_gates", simulated_run)
    result = effective_cutcell.certify_cutcell_geometry(DECK, PROBES, AuditConfig())
    assert result.status == "INCONCLUSIVE" and "sealed t=0" in result.reason


@pytest.mark.solver
@pytest.mark.parametrize("translated", [False, True])
def test_pinned_fds_cutcell_matches_tetrahedral_oracle_and_detects_shift(translated, tmp_path):
    deck = DECK
    if translated:
        deck = deck.replace(
            "0.25,0.25,0.25,0.55,0.25,0.25,0.25,0.55,0.25,0.25,0.25,0.55",
            "0.35,0.25,0.25,0.65,0.25,0.25,0.35,0.55,0.25,0.35,0.25,0.55",
        )
    result = effective_cutcell.certify_cutcell_geometry(
        deck, PROBES, AuditConfig(solver_evidence_directory=str(tmp_path)),
    )
    assert result.status == ("FAIL" if translated else "PASS"), result.reason
    measurements = result.evidence["measurements"]
    assert measurements["global_gas"]["measured"] == pytest.approx(0.9955)
    assert measurements["corner_gas"]["measured"] == pytest.approx(0.001 if translated else 0.000875)
    assert measurements["face_gas"]["measured"] == pytest.approx(0.01 if translated else 0.0075)
    assert len(result.evidence["base_fds_sha256"]) == len(result.evidence["solver_sha256"]) == 64
    assert result.evidence["base_fds_sha256"] != result.evidence["instrumented_fds_sha256"]
    assert Path(result.evidence["directory"], "cutcell-probes.json").is_file()
