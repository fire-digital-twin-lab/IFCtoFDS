"""A reviewed exclusion leaves a P2 finding, so a clean report cannot hide an element missing from the deck."""

from ifc_to_fds.domain.validation.model import GateStatus, Severity
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.mapping.policy import plan_mapping
from ifc_to_fds.validation.engine import run_independent_validation


def test_an_approved_exclusion_is_a_p2_finding_with_its_reviewer_and_rationale(box_model):
    element = next(e for e in box_model.elements if e.role == "PHYSICAL")
    decision = dict(action="EXCLUDE", policy_version="1", reviewer="pccc-eng", evidence="note 7",
                    rationale="Door body is an open surface model; passage modeled open")
    plan_mapping(box_model, decisions={element.entity_key: decision})
    text, _ = serialize_fds(box_model)
    report = run_independent_validation(box_model, text, build_manifest(box_model, text))

    assert report.element_statuses[element.entity_key] == "EXCLUDED_APPROVED"
    found = [f for f in report.findings if f.element_id == element.entity_key and "reviewed decision" in f.detail]
    assert len(found) == 1
    assert found[0].severity == Severity.P2 and found[0].category == "scope"
    assert "pccc-eng" in found[0].detail and "passage modeled open" in found[0].detail
    assert report.gates["scope"].status != GateStatus.FAIL  # information, not a failure
