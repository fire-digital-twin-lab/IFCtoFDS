"""Behavior regressions for the contracts introduced by the modular refactor."""

import json
import pytest

from ifc_to_fds.domain.mapping import build_mapping_plan, MappingStrategy
from ifc_to_fds.domain.validation import ValidationContext, GateResult, GateStatus
from ifc_to_fds.domain.validation.evaluator import AcceptanceEvaluator
from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.domain.scope import ScopeDecision
from ifc_to_fds.mapping.policy import plan_mapping
from tests.baseline.generate_baseline import semantic_csv_hash, assert_fixture_hash


def test_csv_parity_is_semantic_and_fixture_identity_is_exact(tmp_path):
    assert semantic_csv_hash(b'a,b\r\n1,"x\ny"\r\n') == semantic_csv_hash(
        b'a,b\n1,"x\ny"\n'
    )
    assert semantic_csv_hash(b"a,b\n1,2\n") != semantic_csv_hash(b"a,b\n1,3\n")
    p = tmp_path / "fixture.ifc"
    p.write_bytes(b"changed")
    with pytest.raises(AssertionError, match="Fixture bytes differ"):
        assert_fixture_hash(p, {"source_sha256": "original"})


def test_plan_is_authoritative_and_not_mutated(box_model):
    plan = build_mapping_plan(box_model, cell_size=0.5)
    plan.simulation_domain = BoundingBox(
        xmin=-1, xmax=3, ymin=-1, ymax=2, zmin=-1, zmax=4
    )
    plan.decisions[0].strategy = MappingStrategy.NONE
    plan.decisions[0].fds_representation = "NONE"
    before = plan.model_dump()
    text, manifest = serialize_fds(box_model, mapping_plan=plan)
    assert "&OBST" not in text and "&GEOM" not in text
    assert "&MESH IJK=8,6,10, XB=-1,3,-1,2,-1,4 /" in text
    assert manifest.records[0].mapping_strategy == "NONE"
    assert manifest.total_primitives_emitted == 0
    assert manifest.simulation_domain == plan.simulation_domain.model_dump()
    assert plan.model_dump() == before


def test_plan_missing_domain_is_not_implicitly_expanded(box_model):
    plan = build_mapping_plan(box_model)
    plan.simulation_domain = None
    text, manifest = serialize_fds(box_model, mapping_plan=plan)
    assert "&MESH" not in text
    assert manifest.simulation_domain is None


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "cell", "scope", "reference", "bounds", "boundary"],
)
def test_plan_rejects_invalid_authorization(box_model, mutation):
    if mutation == "reference":
        box_model.elements[0].classification_evidence = ["MEP fixture"]
        plan_mapping(box_model)
    plan = build_mapping_plan(box_model)
    kwargs = {}
    if mutation == "missing":
        plan.decisions.clear()
    if mutation == "duplicate":
        plan.decisions.append(plan.decisions[0].model_copy(deep=True))
    if mutation == "cell":
        kwargs["cell_size"] = 0.5
    if mutation == "scope":
        plan.decisions[0].scope_decision = ScopeDecision.OUT_OF_SCOPE
    if mutation == "reference":
        plan.decisions[0].strategy = MappingStrategy.OBST
        plan.decisions[0].fds_representation = "OBST"
    if mutation == "bounds":
        plan.decisions[0].representation_bounds = BoundingBox(
            xmin=0, xmax=1, ymin=0, ymax=1, zmin=0, zmax=3
        )
    if mutation == "boundary":
        plan.simulation_domain = BoundingBox(
            xmin=0.5, xmax=2, ymin=0, ymax=1, zmin=0, zmax=3
        )
    with pytest.raises(ValueError):
        serialize_fds(box_model, mapping_plan=plan, **kwargs)


def test_evaluator_finalizes_and_detaches_outcomes(box_model):
    context = ValidationContext(model=box_model, fds_text="", manifest=None)
    evaluator = AcceptanceEvaluator()
    empty = evaluator.evaluate(context, [])
    assert empty.status == "INCONCLUSIVE"
    failed = CheckerOutcome(
        "geometry",
        GateResult(status=GateStatus.FAIL, evidence={"nested": [1]}),
        metrics={"nested": [1]},
    )
    report = evaluator.evaluate(context, [failed])
    assert report.status == report.mapping_status == "REJECTED"
    failed.result.status = GateStatus.PASS
    failed.result.evidence["nested"].append(2)
    failed.metrics["nested"].append(2)
    assert report.gates["geometry"].status == "FAIL"
    assert report.gates["geometry"].evidence == {"nested": [1]}
    assert report.metrics["nested"] == [1]
    outcomes = [
        CheckerOutcome(name, GateResult(status=GateStatus.PASS)) for name in empty.gates
    ]
    assert evaluator.evaluate(context, outcomes).status == "MAPPING_VERIFIED"
    outcomes[0].result.status = GateStatus.NOT_APPLICABLE
    assert evaluator.evaluate(context, outcomes).status == "INCONCLUSIVE"
    outcomes[0].result.reason = "Not applicable to fixture"
    assert evaluator.evaluate(context, outcomes).status == "MAPPING_VERIFIED"


@pytest.mark.parametrize(
    "mutation", ["none", "approved", "missing", "hash", "content", "payload"]
)
def test_reference_adapter_and_facade_share_integrity(box_model, tmp_path, mutation):
    from tests.test_golden_mapping import checked
    from ifc_to_fds.validation.golden import (
        create_candidate,
        inspect_case,
        bundle_digest,
    )
    from ifc_to_fds.adapters.reference import FilesystemReferenceRepository

    text, manifest, package, report, config = checked(box_model)
    case = tmp_path / "case"
    create_candidate(case, box_model, manifest, package, report, config, text)
    approval_path = case / "approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if mutation == "approved":
        approval.update(
            status="APPROVED", reviewer="fixture-reviewer", evidence=["fixture"]
        )
        approval_path.write_text(json.dumps(approval), encoding="utf-8")
    elif mutation == "missing":
        approval_path.unlink()
    elif mutation in ("hash", "content", "payload"):
        target = case / (
            "scope.json"
            if mutation == "hash"
            else "structural-reference.json"
            if mutation == "content"
            else "geometry-package.json"
        )
        data = json.loads(target.read_text(encoding="utf-8"))
        if mutation == "hash":
            data["changed"] = True
        elif mutation == "content":
            data["unknown:1"] = {}
        else:
            data["elements"]["fixture:1"]["mesh"]["vertices"][0][0] += 1
        target.write_text(json.dumps(data), encoding="utf-8")
        if mutation in ("content", "payload"):
            approval["bundle_sha256"] = bundle_digest(case)
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
    for inspect in (inspect_case, FilesystemReferenceRepository().inspect_case):
        if mutation in ("none", "approved"):
            assert inspect(case)[1]["status"] == (
                "APPROVED" if mutation == "approved" else "DRAFT"
            )
        else:
            with pytest.raises((ValueError, FileNotFoundError)):
                inspect(case)
