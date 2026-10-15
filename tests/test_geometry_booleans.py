import os
from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.geometry.engine import process_model_geometry
from ifc_to_fds.geometry.mesh import inspect_mesh_quality

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_fzk_wall_opening_subtraction():
    fzk_path = os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    model, ifc_file = extract_inventory(fzk_path)

    # Process geometry using IfcOpenShell OpenCASCADE engine
    model = process_model_geometry(model, ifc_file)

    # Find Wand-Ext-ERDG-1 (external wall with 3 openings)
    wall = next((el for el in model.elements if el.name == "Wand-Ext-ERDG-1"), None)
    assert wall is not None
    assert len(wall.openings) == 3
    assert wall.mesh is not None

    # Verify mesh has subtracted openings: uncarved box has exactly 12 faces; carved BRep mesh has 84 faces
    assert len(wall.mesh.faces) > 12
    assert len(wall.mesh.faces) == 84

    # Verify bounding box is non-degenerate (0.3m thick, 10.0m long along Y, 2.7m tall)
    assert wall.bounding_box is not None
    assert round(wall.bounding_box.dx, 2) == 0.30
    assert round(wall.bounding_box.dy, 2) == 10.00
    assert round(wall.bounding_box.dz, 2) == 2.70

    # Audit manifoldness
    quality = inspect_mesh_quality(wall.mesh)
    assert quality["degenerate_faces"] == 0
    assert quality["non_manifold_edges"] == 0
    assert quality["is_closed_manifold"] == 1
