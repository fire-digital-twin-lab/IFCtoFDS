"""Synthetic evidence tests attest integrity, never actual PyroSim execution."""

import copy
import hashlib

import pytest

from ifc_to_fds.modules.verification.api import validate_editor_evidence


def review():
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    return {
        "pyrosim_version": "TEST_FIXTURE_ONLY",
        "reviewer": "synthetic test reviewer",
        "warnings_review": "synthetic diagnostics reviewed",
        "imported_at": "2026-10-23T00:00:00+07:00",
        "import_result": "IMPORTED",
        "source_sha256": digest(b"source"),
        "exported_sha256": digest(b"exported"),
        "project": {"file": "fixture.psm", "sha256": digest(b"project")},
        "diagnostics": {"file": "import.txt", "sha256": digest(b"diagnostics")},
    }


def test_valid_review_is_explicitly_manual():
    gate = validate_editor_evidence(
        review(),
        b"source",
        b"exported",
        {"project": b"project", "diagnostics": b"diagnostics"},
    )
    assert gate.status == "PASS"
    assert gate.evidence["gui_automated"] is False
    assert gate.evidence["method"] == "HUMAN_REVIEW_WITH_HASH_BOUND_ARTIFACTS"


@pytest.mark.parametrize(
    "mutation",
    [
        "reviewer",
        "warnings_review",
        "imported_at",
        "source_sha256",
        "exported_sha256",
        "project",
        "diagnostics",
        "import_result",
    ],
)
def test_changed_or_missing_editor_evidence_is_rejected(mutation):
    document = copy.deepcopy(review())
    document[mutation] = ""
    gate = validate_editor_evidence(
        document,
        b"source",
        b"exported",
        {"project": b"project", "diagnostics": b"diagnostics"},
    )
    assert gate.status == "FAIL"


def test_changed_project_after_review_is_rejected():
    gate = validate_editor_evidence(
        review(),
        b"source",
        b"exported",
        {"project": b"different project", "diagnostics": b"diagnostics"},
    )
    assert gate.status == "FAIL"


def test_attestation_cannot_claim_automated_gui_observation():
    document = {**review(), "gui_automated": True, "method": "AUTOMATED"}
    gate = validate_editor_evidence(
        document,
        b"source",
        b"exported",
        {"project": b"project", "diagnostics": b"diagnostics"},
    )
    assert gate.status == "PASS"
    assert gate.evidence["gui_automated"] is False
    assert gate.evidence["method"] == "HUMAN_REVIEW_WITH_HASH_BOUND_ARTIFACTS"
