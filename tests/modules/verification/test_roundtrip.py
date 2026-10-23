import pytest

from ifc_to_fds.modules.verification.api import compare_roundtrip_geometry
from tests.support.solver_cases import solver_cases


@pytest.mark.parametrize("name", ["obst", "geom"])
def test_identical_roundtrip_proves_static_geometry_only(name):
    text = solver_cases()[name]
    gate = compare_roundtrip_geometry(text, text)
    assert gate.status == "PASS"
    assert gate.evidence["scope"] == "STATIC_GEOMETRY_ONLY"


def test_renamed_id_needs_alias_and_shape_proof():
    text = solver_cases()["obst"]
    renamed = text.replace("ID='wall'", "ID='renamed'")
    assert compare_roundtrip_geometry(text, renamed).status == "FAIL"
    assert (
        compare_roundtrip_geometry(text, renamed, aliases={"wall": "renamed"}).status
        == "PASS"
    )
    changed = renamed.replace("XB=1,3,0.2,1.8,0,2", "XB=1.2,3.2,0.2,1.8,0,2")
    assert (
        compare_roundtrip_geometry(text, changed, aliases={"wall": "renamed"}).status
        == "FAIL"
    )


@pytest.mark.parametrize("mutation", ["missing", "extra", "domain", "invalid_geom"])
def test_roundtrip_does_not_accept_file_creation_as_geometry(mutation):
    cases = solver_cases()
    original = cases["geom"] if mutation == "invalid_geom" else cases["obst"]
    changed = {
        "missing": cases["obst"].replace("&OBST ID='wall', XB=1,3,0.2,1.8,0,2 /\n", ""),
        "extra": cases["obst"].replace(
            "&TAIL", "&OBST ID='extra', XB=0,0.2,0,0.2,0,0.2 /\n&TAIL"
        ),
        "domain": cases["obst"].replace("IJK=20,10,10", "IJK=40,10,10"),
        "invalid_geom": cases["invalid_geom"],
    }[mutation]
    assert compare_roundtrip_geometry(original, changed).status == "FAIL"


@pytest.mark.parametrize("name", ["hole", "vent"])
def test_identical_static_opening_and_boundary_operators_are_preserved(name):
    text = solver_cases()[name]
    gate = compare_roundtrip_geometry(text, text)
    assert gate.status == "PASS"
    operator = "opening" if name == "hole" else "outside"
    assert gate.evidence["comparisons"][operator]["proof"] == "EXACT_STATIC_OPERATOR"


@pytest.mark.parametrize(
    "mutation",
    [
        "hole_shift",
        "vent_surface",
        "surface_definition",
        "hole_host_kind",
        "invalid_vent",
    ],
)
def test_roundtrip_rejects_changed_opening_or_boundary_semantics(mutation):
    cases = solver_cases()
    text = (
        cases["hole"] if mutation in ("hole_shift", "hole_host_kind") else cases["vent"]
    )
    if mutation == "hole_shift":
        changed = text.replace("XB=0.8,3.2,0.6,1.4,0,1.4", "XB=0.8,3.2,0.8,1.4,0,1.4")
    elif mutation == "vent_surface":
        changed = text.replace("SURF_ID='OPEN'", "SURF_ID='INERT'")
    elif mutation == "surface_definition":
        changed = text.replace("&TAIL", "&SURF ID='OPEN', COLOR='RED' /\n&TAIL")
    elif mutation == "invalid_vent":
        changed = text = text.replace("XB=0,0,0,2,0,2", "XB=0,1,0,2,0,2")
    else:
        # HOLE cuts OBST; changing its host to a GEOM cube changes semantics
        # even when the host solid itself remains geometrically equivalent.
        from ifc_to_fds.modules.geometry.api import box_mesh
        from ifc_to_fds.domain.bim import BoundingBox

        mesh = box_mesh(BoundingBox(xmin=1, xmax=3, ymin=0.2, ymax=1.8, zmin=0, zmax=2))
        vertices = ",".join(str(x) for v in mesh.vertices for x in v)
        faces = ",".join(str(x) for f in mesh.faces for x in [*(i + 1 for i in f), 1])
        changed = text.replace(
            "&OBST ID='wall', XB=1,3,0.2,1.8,0,2 /",
            f"&GEOM ID='wall', VERTS={vertices}, FACES={faces} /",
        )
    assert compare_roundtrip_geometry(text, changed).status == "FAIL"


def test_bad_alias_configuration_is_a_diagnostic():
    text = solver_cases()["obst"]
    assert compare_roundtrip_geometry(text, text, aliases={"wall": []}).status == "FAIL"


def test_changed_geom_face_surface_is_not_a_geometric_roundtrip_pass():
    text = solver_cases()["geom"]
    invalid = text.replace("FACES=1,3,2,1", "FACES=1,3,2,999")
    assert compare_roundtrip_geometry(text, invalid).status == "FAIL"
    multiple = text.replace("SURF_ID='solid'", "SURF_ID='solid','INERT'")
    changed = multiple.replace("FACES=1,3,2,1", "FACES=1,3,2,2")
    assert compare_roundtrip_geometry(multiple, changed).status == "INCONCLUSIVE"
