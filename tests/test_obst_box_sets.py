"""A rectilinear host with openings is exported as several &OBST boxes and still verifies."""

import re
from pathlib import Path

from ifc_to_fds.domain.mapping import MappingStrategy
from ifc_to_fds.pipeline import convert

OPENING = str(Path(__file__).parent / "baseline" / "fixtures" / "opening.ifc")


def test_box_sets_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("IFCFDS_OBST_BOX_SETS", "0")
    result = convert([OPENING], output_directory=tmp_path)
    assert "&GEOM" in result["fds_text"]
    wall = next(r for r in result["manifest"]["records"] if r["ifc_type"] == "IfcWall")
    assert wall["mapping_strategy"] == "GEOM"


def test_wall_with_opening_becomes_obst_boxes_not_geom(tmp_path, monkeypatch):
    monkeypatch.setenv("IFCFDS_OBST_BOX_SETS", "1")
    result = convert([OPENING], output_directory=tmp_path)
    text = result["fds_text"]
    assert "&GEOM" not in text
    boxes = re.findall(r"^&OBST ID='OBST_\d+_[^']*'", text, re.M)
    assert len(boxes) >= 2, text[:400]
    wall = next(r for r in result["manifest"]["records"] if r["ifc_type"] == "IfcWall")
    assert wall["mapping_strategy"] == "OBST" and len(wall["fds_primitive_ids"]) == len(boxes)
    assert result["status"] == "MAPPING_VERIFIED", result["report"]["gates"]


def test_sloped_solid_stays_geom():
    from ifc_to_fds.geometry.rectilinear import rectilinear_boxes
    import trimesh
    from ifc_to_fds.domain.bim import TriangleMesh

    wedge = trimesh.creation.box()
    wedge.vertices[wedge.vertices[:, 2] > 0, 0] += 0.3
    assert rectilinear_boxes(TriangleMesh(vertices=wedge.vertices.tolist(), faces=wedge.faces.tolist())) is None


def test_host_whose_opening_was_not_subtracted_stays_geom(monkeypatch):
    monkeypatch.setenv("IFCFDS_OBST_BOX_SETS", "1")
    """A plain-box host with an unproven void must never become a solid OBST that fills the opening."""
    from ifc_to_fds.application.services.model_preparer import prepare_model
    from ifc_to_fds.domain.bim import OpeningReference
    from ifc_to_fds.mapping.policy import determine_element_strategy

    model = prepare_model([OPENING], {})
    wall = next(e for e in model.elements if e.ifc_type == "IfcWall")
    assert determine_element_strategy(wall) == MappingStrategy.OBST  # opening really subtracted: boxes
    # Pretend the void was not cut: the host mesh is then the full block and still overlaps the opening.
    import trimesh
    from ifc_to_fds.domain.bim import TriangleMesh
    full = trimesh.creation.box(bounds=[(0, 0, 0), (4, 0.3, 3)])
    wall.mesh = TriangleMesh(vertices=full.vertices.tolist(), faces=full.faces.tolist())
    assert determine_element_strategy(wall) == MappingStrategy.GEOM


def test_box_covers_never_make_an_audited_model_worse(monkeypatch):
    """On FZK-Haus no element may become DEVIATED because it was exported as a box cover."""
    monkeypatch.setenv("IFCFDS_OBST_BOX_SETS", "1")
    result = convert([str(Path(__file__).resolve().parents[1] / "examples" / "AC20-FZK-Haus.ifc")])
    statuses = result["report"]["element_statuses"].values()
    assert "DEVIATED" not in statuses
    assert not [f for f in result["report"]["findings"] if f["category"] == "openings"]
