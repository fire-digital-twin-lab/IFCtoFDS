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
