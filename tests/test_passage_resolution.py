"""A grid too coarse for an opening or a thin wall is reported by name with the cell size that fixes it."""

from pathlib import Path

from ifc_to_fds.pipeline import convert

OPENING = str(Path(__file__).parent / "baseline" / "fixtures" / "opening.ifc")


def _resolution(result):
    gate = result["report"]["gates"]["passage_resolution"]
    findings = [f for f in result["report"]["findings"] if f["category"] == "passage_resolution"]
    return gate, findings


def test_default_grid_resolves_the_opening_fixture():
    gate, findings = _resolution(convert([OPENING], configuration={"cell_size": 0.2}))
    assert gate["status"] == "PASS" and not findings


def test_coarse_grid_fails_by_name_and_proposes_a_cell_size():
    result = convert([OPENING], configuration={"cell_size": 1.0})
    gate, findings = _resolution(result)
    assert gate["status"] == "FAIL", gate
    assert findings and all(f["verification_level"] == "simulation" for f in findings)
    assert any("Use cells of at most" in f["detail"] for f in findings)
    # The mapping is still right; only the simulation cannot rely on this grid.
    assert result["mapping_status"] == "MAPPING_VERIFIED"
    assert result["simulation_status"] == "REJECTED"
    ok = convert([OPENING], configuration={"cell_size": 0.2})
    assert ok["simulation_status"] == "INCONCLUSIVE"  # unchanged when the grid resolves everything


def test_proposed_cell_size_actually_resolves_the_passage():
    coarse = convert([OPENING], configuration={"cell_size": 1.0})
    _, findings = _resolution(coarse)
    sizes = [float(f["detail"].rsplit("at most ", 1)[1].split(" ")[0]) for f in findings if "narrower" in f["title"]]
    assert sizes, findings
    gate, _ = _resolution(convert([OPENING], configuration={"cell_size": min(sizes)}))
    assert gate["status"] == "PASS", gate


def _deck_checker(box_model, ifc_type, xb, cell=0.2):
    """Run the gate on a one-element deck: `xb` box of `ifc_type` in a [0,2]^3 domain on `cell` m cells."""
    from ifc_to_fds.domain.bim import BoundingBox
    from ifc_to_fds.domain.validation.model import ValidationContext
    from ifc_to_fds.geometry.mesh import box_mesh
    from ifc_to_fds.mapping.exporter import serialize_fds
    from ifc_to_fds.validation.parser import parse_fds
    from ifc_to_fds.validation.passage_resolution import PassageResolutionChecker

    bounds = BoundingBox(xmin=xb[0], xmax=xb[1], ymin=xb[2], ymax=xb[3], zmin=xb[4], zmax=xb[5])
    element = box_model.elements[0]
    element.ifc_type, element.bounding_box, element.mesh = ifc_type, bounds, box_mesh(bounds)
    box_model.simulation_domain = BoundingBox(xmin=0, xmax=2, ymin=0, ymax=2, zmin=0, zmax=2)
    text, _ = serialize_fds(box_model, cell_size=cell)
    return PassageResolutionChecker().check(ValidationContext(model=box_model, fds_text=text, manifest=None, parsed_fds=parse_fds(text)))


BEAM = [0.34, 0.42, 0.34, 0.42, 1.0, 1.8]  # audit F4: 0.08 x 0.08 x 0.80 m, both small faces snap to one plane


def test_a_beam_that_collapses_to_a_line_on_the_grid_is_reported(box_model):
    outcome = _deck_checker(box_model, "IfcBeam", BEAM)
    assert outcome.result.status == "FAIL", outcome.result
    assert "vanishes" in outcome.findings[0].title and "Use cells of at most 0.080" in outcome.findings[0].detail
    assert outcome.findings[0].verification_level == "simulation"


def test_the_same_box_as_a_wall_is_still_reported(box_model):
    assert _deck_checker(box_model, "IfcWall", BEAM).result.status == "FAIL"


def test_a_beam_thick_enough_for_the_grid_passes(box_model):
    outcome = _deck_checker(box_model, "IfcBeam", [0.30, 0.70, 0.30, 0.70, 1.0, 1.8])
    assert outcome.result.status == "PASS", outcome.result


def test_a_non_enclosure_solid_thin_on_one_axis_is_not_a_finding(box_model):
    # a 0.08 m slab on a 0.2 m grid becomes one thin plane, which FDS keeps: only walls, slabs and roofs report it
    assert _deck_checker(box_model, "IfcBeam", [0.30, 0.70, 0.34, 0.42, 1.0, 1.8]).result.status == "PASS"
    assert _deck_checker(box_model, "IfcWall", [0.30, 0.70, 0.34, 0.42, 1.0, 1.8]).result.status == "FAIL"


def _audit_with_meshes(tmp_path, meshes, *, obst_xb=None):
    import hashlib
    import re

    from ifc_to_fds.domain.mapping import MappingManifest
    from ifc_to_fds.pipeline import audit

    base = convert([OPENING], output_directory=tmp_path)
    text = re.sub(r"(?m)^&MESH .*? /$", meshes, base["fds_text"], count=1)
    assert text != base["fds_text"]
    if obst_xb is not None:
        text, changed = re.subn(r"(?m)^(&OBST [^\n]*?\bXB=)[-0-9.eE+]+(?:,[-0-9.eE+]+){5}",
                                lambda match: match[1] + obst_xb, text, count=1)
        assert changed == 1
    manifest = MappingManifest.model_validate(base["manifest"])
    manifest.fds_sha256 = hashlib.sha256(text.encode()).hexdigest()
    manifest.reseal()
    return audit([OPENING], text, manifest, base["configuration"], base["geometry_package"])[2]


SEAM = (
    "&MESH ID='M1', IJK=1,2,15, XB=0,0.5,0,0.3,0,3 /\n"
    "&MESH ID='M2', IJK=2,2,15, XB=0.5,4,0,0.3,0,3 /"
)


def test_an_opening_across_a_mesh_seam_is_not_reported_as_resolved(tmp_path):
    """Audit F3: the wall boxes were counted as assessed and hid the opening that could not be estimated."""
    report = _audit_with_meshes(tmp_path, SEAM)
    gate = report.gates["passage_resolution"]
    assert gate.status == "INCONCLUSIVE", gate
    assert gate.evidence["openings_not_estimated"] >= 1 and gate.evidence["assessed"] >= 1
    assert "not estimated" in gate.reason
    assert report.mapping_status == "MAPPING_VERIFIED"  # only the simulation verdict is affected


def test_a_single_mesh_still_passes_when_every_opening_is_estimated(tmp_path):
    gate = _audit_with_meshes(tmp_path, "&MESH ID='M1', IJK=20,2,15, XB=0,4,0,0.3,0,3 /").gates["passage_resolution"]
    assert gate.status == "PASS" and gate.evidence["openings_not_estimated"] == 0

def test_a_vanishing_solid_takes_priority_over_an_unestimated_opening(tmp_path):
    report = _audit_with_meshes(tmp_path, SEAM, obst_xb="0.34,0.42,0.034,0.042,1.0,1.8")
    gate = report.gates["passage_resolution"]
    assert gate.status == "FAIL", gate
    assert gate.evidence["openings_not_estimated"] > 0
    assert any("Solid vanishes on the grid" in f.title for f in report.findings)
