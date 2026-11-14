import re
import pytest
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.manifest import build_manifest
from ifc_to_fds.validation.engine import run_independent_validation
from ifc_to_fds.validation.acceptance import AcceptanceReport, GateResult
from ifc_to_fds.domain.validation.model import REQUIRED_MAPPING_GATES
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
        gates = {
            name: GateResult(status="PASS") for name in REQUIRED_MAPPING_GATES
        }
        gates["syntax"] = GateResult(status=status)
        report = AcceptanceReport(gates=gates)
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
        gates={
            **{name: GateResult(status="PASS") for name in REQUIRED_MAPPING_GATES},
            **sim_gates,
        }
    )
    finalized = report.finalize()
    assert finalized.mapping_status == AcceptanceStatus.MAPPING_VERIFIED
    assert finalized.simulation_status != AcceptanceStatus.SIMULATION_VERIFIED
    assert finalized.simulation_status == AcceptanceStatus.INCONCLUSIVE

    failing = AcceptanceReport(
        gates={
            **{name: GateResult(status="PASS") for name in REQUIRED_MAPPING_GATES},
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


def test_empty_fds_text_is_rejected_not_crash(box_model):
    """Engine on an empty FDS artifact: no crash, fail closed, solver never runs."""
    report = run_independent_validation(box_model, "", build_manifest(box_model, ""))
    assert report.status == "REJECTED"
    for name in ("syntax", "traceability", "structural_completeness", "air_path"):
        assert report.gates[name].status == "FAIL", name
    for name in ("solver", "effective_geometry"):
        assert report.gates[name].status == "NOT_RUN", name


def test_empty_fds_text_never_certifies_geometry(box_model):
    """No solid could be compared, so the geometry gate must not say PASS; the verdict stays fail-closed."""
    from ifc_to_fds.domain.validation.model import GateStatus

    report = run_independent_validation(box_model, "", build_manifest(box_model, ""))
    assert report.gates["geometry"].status == GateStatus.INCONCLUSIVE
    assert "No solid comparison completed" in report.gates["geometry"].reason
    assert report.status.value == "REJECTED"  # syntax and traceability fail closed


def test_parser_whitelists_fire_namelists_and_surf_combustion_properties():
    fds = """
&HEAD CHID='fire_test', TITLE='EV Fire Scenario' /
&TIME T_END=600.0 /
&MESH ID='M1', IJK=10,10,10, XB=0,2,0,2,0,2 /
&REAC ID='REAC_EV', FUEL='OFFGAS', C=2.0, H=4.0, O=1.0, CO_YIELD=0.1, SOOT_YIELD=0.1 /
&RAMP ID='RAMP_Q', T=0.0, F=0.0 /
&RAMP ID='RAMP_Q', T=100.0, F=1.0 /
&SURF ID='BURNER', HRRPUA=1500.0, RAMP_Q='RAMP_Q' /
&DEVC ID='HEAT_1', QUANTITY='TEMPERATURE', XYZ=1.0,1.0,1.8 /
&CTRL ID='CTRL_1', FUNCTION_TYPE='ANY', INPUT_ID='HEAT_1' /
&OBST ID='OBST_1', XB=0.5,1.5,0.5,1.5,0,0.5, SURF_ID='INERT', CTRL_ID='CTRL_1' /
&VENT ID='VENT_1', XB=0.5,1.5,0.5,1.5,0.5,0.5, SURF_ID='BURNER' /
&TAIL /
"""
    parsed = parse_fds(fds)
    assert not parsed.errors
    assert not parsed.unsupported


def test_parser_whitelists_hvac_namelists():
    fds = """
&HEAD CHID='hvac_test', TITLE='HVAC Duct Scenario' /
&TIME T_END=100.0 /
&MESH ID='M1', IJK=10,10,10, XB=0,2,0,2,0,2 /
&HVAC TYPE_ID='NODE', ID='N1', DUCT_ID='D1', XYZ=0.5,1.0,1.5, AMBIENT=.TRUE. /
&HVAC TYPE_ID='NODE', ID='N2', DUCT_ID='D1', XYZ=1.5,1.0,1.5, AMBIENT=.TRUE. /
&HVAC TYPE_ID='DUCT', ID='D1', NODE_ID='N1','N2', AREA=0.1, LENGTH=1.0, ROUGHNESS=0.001 /
&TAIL /
"""
    parsed = parse_fds(fds)
    assert not parsed.errors
    assert not parsed.unsupported



@pytest.mark.xfail(
    strict=True,
    reason=(
        "Engine traceability has no scenario-primitive allowance (OBST_EV_*, VENT_BURNER_*); "
        "that skip lived only in the removed TraceabilityChecker. Production audits the base "
        "FDS before scenario composition, so this is latent."
    ),
)
def test_traceability_skips_scenario_fire_primitives(box_model):
    text, _ = serialize_fds(box_model)
    fire_fragment = """
&OBST ID='OBST_EV_1', XB=0.5,1.5,0.5,1.5,0,0.5, SURF_ID='INERT' /
&VENT ID='VENT_BURNER_1', XB=0.5,1.5,0.5,1.5,0.5,0.5, SURF_ID='BURNER' /
"""
    combined_fds = text.replace("&TAIL /", fire_fragment + "\n&TAIL /")
    report = audit(box_model, combined_fds)
    assert report.gates["traceability"].status == "PASS"
    assert "OBST_EV_1" not in str(report.findings)
    assert "VENT_BURNER_1" not in str(report.findings)


def test_air_path_negative_leak_is_inconclusive(monkeypatch, box_model):
    """C-1 regression test: Negative leak volume (inverted normals) must return INCONCLUSIVE, never PASS."""
    from ifc_to_fds.domain.validation.model import ValidationContext, GateStatus
    from ifc_to_fds.validation.checkers.air_path import AirPathTopologyChecker
    import ifc_to_fds.validation.checkers.air_path as ap_mod

    text, manifest = serialize_fds(box_model)
    ctx = ValidationContext(
        model=box_model,
        fds_text=text,
        manifest=manifest,
        parsed_fds=parse_fds(text),
    )

    orig_sb = ap_mod.solid_boolean

    class MockInvertedMesh:
        volume = -0.1018
        is_volume = True

    def mock_sb(meshes, op):
        if op == "intersection" and len(meshes) == 2:
            return MockInvertedMesh()
        return orig_sb(meshes, op)

    monkeypatch.setattr(ap_mod, "solid_boolean", mock_sb)
    outcome = AirPathTopologyChecker().check(ctx)
    assert outcome.result.status == GateStatus.INCONCLUSIVE
    assert "INVALID_VOLUME_SIGN" in outcome.result.reason


def test_thin_or_open_covering_classified_as_semantic_only(box_model):
    from ifc_to_fds.core.canonical import CanonicalElement, MappingStrategy, MappingStatus, TriangleMesh
    from ifc_to_fds.mapping.policy import plan_mapping

    thin_mesh = TriangleMesh(
        vertices=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0]],
        faces=[[0, 1, 2]],
    )
    covering = CanonicalElement(
        global_id="covering_1",
        step_id=999,
        ifc_type="IfcCovering",
        name="Wall Paint Finish",
        mesh=thin_mesh,
    )
    box_model.elements.append(covering)
    plan_mapping(box_model)

    assert covering.mapping_strategy == MappingStrategy.SEMANTIC_ONLY
    assert covering.mapping_status == MappingStatus.SEMANTIC_ONLY
    assert covering.simulation_role == "REFERENCE_GEOMETRY"



def _legacy_text(box_model):
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
    return legacy_text


def test_traceability_legacy_provenance_resolves_through_engine(box_model):
    """Legacy '! IFC entity #id GUID=..' provenance resolves to the element: no missing P0."""
    from ifc_to_fds.domain.validation.model import Severity

    report = audit(box_model, _legacy_text(box_model))
    missing = [
        f
        for f in report.findings
        if "Missing required FDS solid" in f.title and f.severity == Severity.P0
    ]
    assert missing == []
    assert report.element_statuses[box_model.elements[0].entity_key] == "MATCHED"


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


def test_traceability_repeat_validations_are_stable(box_model):
    legacy_text = _legacy_text(box_model)
    first = audit(box_model, legacy_text)
    second = audit(box_model, legacy_text)
    assert (second.gates["traceability"].status, second.gates["traceability"].reason) == (
        first.gates["traceability"].status,
        first.gates["traceability"].reason,
    )
    assert second.element_statuses == first.element_statuses
