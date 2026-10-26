import trimesh
from ifc_to_fds.core.canonical import TriangleMesh, OpeningReference
from ifc_to_fds.geometry.mesh import as_trimesh, box_mesh
from ifc_to_fds.validation.metrics import opening_residual, passage_metrics


def test_host_cut_and_blocked_passage(box_model):
    original = box_model.elements[0].mesh
    from ifc_to_fds.core.canonical import BoundingBox

    opening = box_mesh(
        BoundingBox(xmin=0.5, xmax=1.5, ymin=-0.1, ymax=1.1, zmin=0.5, zmax=2.0)
    )
    cut = trimesh.boolean.difference(
        [as_trimesh(original), as_trimesh(opening)], engine="manifold"
    )
    carved = TriangleMesh(vertices=cut.vertices.tolist(), faces=cut.faces.tolist())
    assert opening_residual([carved], opening) < 1e-6
    assert opening_residual([original], opening) > 0.5
    correct = passage_metrics([carved], [carved], opening)
    assert correct["normalized_symmetric_difference"] < 1e-6
    blocked = passage_metrics([carved], [carved, original], opening)
    assert blocked["normalized_symmetric_difference"] > 0.5
    # A legitimate closed fill is not a subtraction failure.
    closed = passage_metrics([carved, original], [carved, original], opening)
    assert closed["normalized_symmetric_difference"] < 1e-6


def test_validator_rejects_resealed_geom_even_with_matching_provenance(box_model):
    from ifc_to_fds.core.canonical import BoundingBox
    from ifc_to_fds.mapping.policy import plan_mapping
    from ifc_to_fds.mapping.exporter import serialize_fds
    from ifc_to_fds.mapping.manifest import build_manifest
    from ifc_to_fds.validation.engine import run_independent_validation

    wall = box_model.elements[0]
    solid = wall.mesh.model_copy(deep=True)
    opening = box_mesh(
        BoundingBox(xmin=0.5, xmax=1.5, ymin=-0.1, ymax=1.1, zmin=0.5, zmax=2.0)
    )
    carved = trimesh.boolean.difference(
        [as_trimesh(solid), as_trimesh(opening)], engine="manifold"
    )
    wall.mesh = TriangleMesh(
        vertices=carved.vertices.tolist(), faces=carved.faces.tolist()
    )
    wall.openings = [
        OpeningReference(
            opening_global_id="void-guid",
            opening_step_id=9,
            opening_name="Void",
            mesh=opening,
        )
    ]
    plan_mapping(box_model, force_all_geom=True)
    mutant = box_model.model_copy(deep=True)
    mutant.elements[0].mesh = solid
    text, _ = serialize_fds(mutant)
    box_model.elements[0].fds_primitive_ids = mutant.elements[0].fds_primitive_ids
    report = run_independent_validation(
        box_model, text, build_manifest(box_model, text)
    )
    assert report.status == "REJECTED"
    assert report.gates["geometry"].status == "FAIL"
    assert report.gates["openings"].status == "FAIL"
    assert report.gates["openings"].reason != ""
    assert "void-guid" in report.gates["openings"].reason
    assert report.gates["openings"].evidence
    assert any("void-guid" in f.detail for f in report.findings)
