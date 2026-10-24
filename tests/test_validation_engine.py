import re
import pytest
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.acceptance import AcceptanceReport, GateResult
from ifc_to_fds.validation.parser import parse_fds


def audit(model, text):
    # Update the checksum deliberately: mutations must be caught geometrically,
    # not merely because the bytes changed.
    return run_independent_validation(model, text, build_manifest(model, text))


def test_no_solver_is_inconclusive(box_model):
    text, _ = serialize_fds(box_model)
    report = audit(box_model, text)
    assert report.status == "INCONCLUSIVE"
    assert report.gates["geometry"].status == "PASS"
    assert report.gates["source_inventory"].status == "INCONCLUSIVE"
    assert "Model satisfies all" not in report.to_markdown()


def test_shifted_wall_rejected_with_same_ids(box_model):
    text, _ = serialize_fds(box_model)
    text = text.replace(
        "XB=0,2,0,1,0,3",
        "XB=2.0000,4.0000,0.0000,1.0000,0.0000,3.0000",
    )
    report = audit(box_model, text)
    assert report.status == "REJECTED"
    assert report.gates["geometry"].status == "FAIL"
    assert any(
        f.element_id == "fixture:1" and f.category == "geometry"
        for f in report.findings
    )


def test_missing_and_unexpected_primitives(box_model):
    text, _ = serialize_fds(box_model)
    missing = re.sub(r"&OBST[^/]+/", "", text)
    report = audit(box_model, missing)
    assert report.status == "REJECTED" and report.missing_count == 1
    unexpected = text.replace('"entity_key": "fixture:1"', '"entity_key": "unknown:2"')
    assert audit(box_model, unexpected).gates["traceability"].status == "FAIL"


def test_invalid_face_indices(box_model):
    from ifc_to_fds.mapping.policy import plan_mapping

    plan_mapping(box_model, force_all_geom=True)
    text, _ = serialize_fds(box_model)
    text = text.replace("FACES=", "FACES=99999,2,3,1,", 1)
    assert audit(box_model, text).gates["syntax"].status == "FAIL"


def test_namelist_quotes_exponent_multiline(box_model):
    text, _ = serialize_fds(box_model)
    text = text.replace(
        "TITLE='IFCtoFDS conversion; see acceptance report'",
        "TITLE='a, b / c ! d '' quoted'",
    )
    text = text.replace("XB=0.0000,2.0000", "XB=0D0,\n 2e0")
    parsed = parse_fds(text)
    assert not parsed.errors
    assert next(r for r in parsed.records if r.kind == "HEAD").values["TITLE"] == [
        "a, b / c ! d ' quoted"
    ]


@pytest.mark.parametrize(
    "suffix",
    [
        "&GEOM ID='broken', VERTS=1,2 /",
        "&OBST ID='x', XB=nan,1,0,1,0,1 /",
        "&MYSTERY FOO=1 /",
    ],
)
def test_malformed_or_unsupported_never_pass(box_model, suffix):
    text, _ = serialize_fds(box_model)
    report = audit(box_model, text.replace("&TAIL /", suffix + "\n&TAIL /"))
    assert report.status != "VERIFIED"
    assert report.gates["syntax"].status in ("FAIL", "INCONCLUSIVE")


def test_gate_truth_table():
    for status, verdict in [
        ("PASS", "MAPPING_VERIFIED"),
        ("NOT_RUN", "INCONCLUSIVE"),
        ("INCONCLUSIVE", "INCONCLUSIVE"),
        ("FAIL", "REJECTED"),
    ]:
        report = AcceptanceReport(gates={"required": GateResult(status=status)})
        assert report.finalize().status == verdict
    report = AcceptanceReport(
        gates={"a": GateResult(status="FAIL"), "b": GateResult(status="NOT_RUN")}
    )
    assert report.finalize().status == "REJECTED"


def test_finalize_never_issues_simulation_verified():
    """M13 contract: SIMULATION_VERIFIED is unreachable until the simulation epic.

    finalize() only assigns simulation_status REJECTED/INCONCLUSIVE. Even with
    every simulation gate PASSed, the verdict must stay INCONCLUSIVE -- if a
    future change makes SIMULATION_VERIFIED reachable, this test must fail
    loudly so the checkpoint semantics in convert_verified.py get revisited.
    """
    from ifc_to_fds.domain.validation.model import AcceptanceStatus

    sim_gates = {
        name: GateResult(status="PASS")
        for name in (
            "solver",
            "effective_geometry",
            "physics",
            "scenario",
            "mesh_resolution",
            "operational_model",
        )
    }
    report = AcceptanceReport(
        gates={"required": GateResult(status="PASS"), **sim_gates}
    )
    finalized = report.finalize()
    assert finalized.mapping_status == AcceptanceStatus.MAPPING_VERIFIED
    assert finalized.simulation_status != AcceptanceStatus.SIMULATION_VERIFIED
    assert finalized.simulation_status == AcceptanceStatus.INCONCLUSIVE

    failing = AcceptanceReport(
        gates={
            "required": GateResult(status="PASS"),
            **{**sim_gates, "solver": GateResult(status="FAIL")},
        }
    ).finalize()
    assert failing.simulation_status == AcceptanceStatus.REJECTED


def test_geom_vertex_mutation_and_duplicate_id(box_model):
    from ifc_to_fds.mapping.policy import plan_mapping

    plan_mapping(box_model, force_all_geom=True)
    text, _ = serialize_fds(box_model)
    parsed = parse_fds(text)
    assert any(r.kind == "GEOM" for r in parsed.primitives)

    # Shift all X coordinates while keeping all source metadata and IDs.
    def shift(match):
        values = match.group(1).replace("\n", "").replace(" ", "").strip(",").split(",")
        return (
            "VERTS="
            + ",".join(
                str(float(v) + (2 if i % 3 == 0 else 0)) for i, v in enumerate(values)
            )
            + ",\n FACES="
        )

    shifted = re.sub(r"VERTS=([\s\S]*?),\s*FACES=", shift, text, count=1)
    assert audit(box_model, shifted).gates["geometry"].status == "FAIL"
    geom_block = re.search(r"&GEOM[\s\S]*?/", text).group(0)
    assert (
        audit(box_model, text.replace("&TAIL /", geom_block + "\n&TAIL /"))
        .gates["syntax"]
        .status
        == "FAIL"
    )


def test_self_intersecting_components_are_rejected(box_model):
    import trimesh
    from ifc_to_fds.core.canonical import TriangleMesh
    from ifc_to_fds.geometry.mesh import as_trimesh, has_self_intersection

    a = as_trimesh(box_model.elements[0].mesh)
    b = a.copy()
    b.apply_translation([0.5, 0, 0])
    combined = trimesh.util.concatenate([a, b])
    mesh = TriangleMesh(
        vertices=combined.vertices.tolist(), faces=combined.faces.tolist()
    )
    assert has_self_intersection(mesh)


def test_openings_gate_not_applicable_when_hosts_do_not_emit(box_model):
    from ifc_to_fds.domain.bim import OpeningReference
    from ifc_to_fds.domain.mapping import MappingStrategy
    from ifc_to_fds.domain.validation import GateStatus

    e = box_model.elements[0]
    e.mapping_strategy = MappingStrategy.EXCLUDED_APPROVED
    e.review_status = "EXCLUDED_APPROVED"
    e.fds_representation = "NONE"
    e.openings = [
        OpeningReference(
            entity_key="fixture:opening1",
            host_entity_key=e.entity_key,
            void_relation_key="fixture:void1",
            placement={},
            opening_global_id="opening_guid",
            opening_step_id=999,
            opening_name="Void",
            opening_type="IfcOpeningElement",
        )
    ]
    text, _ = serialize_fds(box_model)
    report = audit(box_model, text)
    assert report.gates["openings"].status == GateStatus.NOT_APPLICABLE
    assert "No mapped host has source openings" in report.gates["openings"].reason


def _fds_with_comment(comment, obst_id="o1"):
    return (
        "&HEAD CHID='t', TITLE='t' /\n"
        "&TIME T_END=1.0 /\n"
        "&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n"
        f"{comment}\n"
        f"&OBST ID='{obst_id}', XB=0,1,0,1,0,1 /\n"
        "&TAIL /\n"
    )


def test_ifc_entity_comment_without_identifiers_leaves_source_empty():
    parsed = parse_fds(_fds_with_comment("! IFC entity list reviewed"))
    obst = next(r for r in parsed.records if r.kind == "OBST")
    assert obst.source == {}


def test_ifc_entity_comment_with_identifiers_sets_legacy_provenance():
    parsed = parse_fds(_fds_with_comment("! IFC entity #123 GUID=abc", obst_id="o2"))
    obst = next(r for r in parsed.records if r.kind == "OBST")
    assert obst.source.get("legacy") is True
    assert obst.source.get("step_id") == 123
    assert obst.source.get("global_id") == "abc"


def test_empty_fds_text_yields_inconclusive_gates_not_crash(box_model):
    from ifc_to_fds.domain.validation.model import GateStatus
    from ifc_to_fds.validation.runner import ValidationRunner

    manifest = build_manifest(box_model, "")
    report = ValidationRunner().validate(box_model, "", manifest)
    assert report.gates["syntax"].status == GateStatus.INCONCLUSIVE
    assert report.gates["representation"].status == GateStatus.INCONCLUSIVE
    assert report.gates["traceability"].status == GateStatus.INCONCLUSIVE
    for name in ("syntax", "representation", "traceability"):
        assert "Incomplete diagnostic artifact" in report.gates[name].reason


def test_empty_fds_text_yields_inconclusive_for_remaining_gates(box_model):
    """P1: boundary/mep/air_path/solver must also return INCONCLUSIVE (not
    crash, FAIL, or PASS) on empty FDS text."""
    from ifc_to_fds.domain.validation.model import GateStatus
    from ifc_to_fds.validation.runner import ValidationRunner

    manifest = build_manifest(box_model, "")
    report = ValidationRunner().validate(box_model, "", manifest)
    for name in ("boundary", "mep", "air_path", "solver"):
        assert report.gates[name].status == GateStatus.INCONCLUSIVE, name
        assert "Incomplete diagnostic artifact" in report.gates[name].reason, name


def test_empty_fds_text_all_runner_gates_pinned(box_model):
    """M10: pin ALL 12 runner checkers on empty FDS text -- 11 must return
    INCONCLUSIVE; solver must also return INCONCLUSIVE (parsed is None so the
    syntax-gated NOT_RUN branch is not reached). scope/domain/geometry/
    structural_completeness/openings are pinned here beyond the syntax/
    representation/traceability gates pinned above."""
    from ifc_to_fds.domain.validation.model import GateStatus
    from ifc_to_fds.validation.runner import ValidationRunner

    manifest = build_manifest(box_model, "")
    report = ValidationRunner().validate(box_model, "", manifest)
    for name in (
        "syntax",
        "domain",
        "traceability",
        "scope",
        "geometry",
        "structural_completeness",
        "air_path",
        "openings",
        "mep",
        "representation",
        "boundary",
        "solver",
    ):
        assert report.gates[name].status == GateStatus.INCONCLUSIVE, name
        assert "Incomplete diagnostic artifact" in report.gates[name].reason, name
    # source_inventory is evaluator-owned (no runner checker emits it), so it
    # stays at the NOT_RUN default -- assert explicitly, not as INCONCLUSIVE.
    assert report.gates["source_inventory"].status == GateStatus.NOT_RUN


def test_traceability_legacy_backfill_writes_entity_key_standalone(box_model):
    from ifc_to_fds.domain.validation.model import Severity, ValidationContext
    from ifc_to_fds.validation.checkers.traceability import TraceabilityChecker

    text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, text)
    parsed = parse_fds(text)
    assert len(parsed.primitives) == 1
    prim = parsed.primitives[0]
    e = box_model.elements[0]
    # Simulate legacy FDS: strip resolved entity_key, keep a uniquely
    # matching global_id + step_id pair.
    prim.source.pop("entity_key", None)
    prim.source["legacy"] = True
    prim.source["global_id"] = e.global_id
    prim.source["step_id"] = e.step_id
    ctx = ValidationContext(
        model=box_model, fds_text=text, manifest=manifest, parsed_fds=parsed
    )
    outcome = TraceabilityChecker().check(ctx)
    assert prim.source.get("entity_key") == e.entity_key
    missing = [
        f
        for f in outcome.findings
        if "Missing required FDS solid" in f.title and f.severity == Severity.P0
    ]
    assert missing == []


def test_ifc_entity_comment_without_identifiers_resets_prior_source():
    text = (
        "&HEAD CHID='t', TITLE='t' /\n"
        "&TIME T_END=1.0 /\n"
        "&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n"
        '! IFC_SOURCE {"entity_key": "A"}\n'
        "! IFC entity list reviewed\n"
        "&OBST ID='o3', XB=0,1,0,1,0,1 /\n"
        "&TAIL /\n"
    )
    parsed = parse_fds(text)
    obst = next(r for r in parsed.records if r.kind == "OBST")
    assert obst.source == {}


def test_traceability_checker_repeat_validates_are_stable(box_model):
    from ifc_to_fds.domain.validation.model import ValidationContext
    from ifc_to_fds.validation.checkers.traceability import TraceabilityChecker

    text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, text)
    parsed = parse_fds(text)
    assert len(parsed.primitives) == 1
    prim = parsed.primitives[0]
    e = box_model.elements[0]
    # Simulate legacy FDS: strip resolved entity_key, keep a uniquely
    # matching global_id + step_id pair.
    prim.source.pop("entity_key", None)
    prim.source["legacy"] = True
    prim.source["global_id"] = e.global_id
    prim.source["step_id"] = e.step_id
    ctx = ValidationContext(
        model=box_model, fds_text=text, manifest=manifest, parsed_fds=parsed
    )
    checker = TraceabilityChecker()
    first = checker.check(ctx)
    second = checker.check(ctx)
    assert (second.result.status, second.result.reason) == (
        first.result.status,
        first.result.reason,
    )


def test_runner_create_context_backfills_legacy_entity_key(box_model):
    """M9: the runner pre-backfill path (runner.py create_context) resolves
    legacy provenance to entity_key independent of any checker -- pairs with
    test_traceability_legacy_backfill_writes_entity_key_standalone to prove the
    runner path works standalone, not just TraceabilityChecker.check."""
    from ifc_to_fds.validation.runner import ValidationRunner

    text, _ = serialize_fds(box_model)
    e = box_model.elements[0]
    legacy_text = re.sub(
        r"^! IFC_SOURCE .*$",
        f"! IFC entity #{e.step_id} GUID={e.global_id}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    assert legacy_text != text
    pre = parse_fds(legacy_text)
    pre_prim = next(p for p in pre.primitives if p.kind == "OBST")
    assert "entity_key" not in pre_prim.source
    assert pre_prim.source.get("legacy") is True

    ctx = ValidationRunner().create_context(
        box_model, legacy_text, build_manifest(box_model, legacy_text)
    )
    assert ctx.parsed_fds is not None
    prim = next(p for p in ctx.parsed_fds.primitives if p.kind == "OBST")
    assert prim.source.get("entity_key") == e.entity_key

