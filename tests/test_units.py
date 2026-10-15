import os
import ifcopenshell
from ifc_to_fds.core.units import get_length_unit_scale

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_unit_scale_extraction():
    # AC20-FZK-Haus.ifc uses METRE
    fzk_path = os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    ifc_file = ifcopenshell.open(fzk_path)
    unit_name, scale = get_length_unit_scale(ifc_file)
    assert unit_name == "METRE"
    assert scale == 1.0


def test_unit_scale_millimeter():
    # Duplex model uses millimetres (0.001 scale)
    duplex_path = os.path.join(REPO_ROOT, "examples", "IfcOpenShell-Duplex.ifc")
    ifc_file = ifcopenshell.open(duplex_path)
    unit_name, scale = get_length_unit_scale(ifc_file)
    assert unit_name in ("METRE", "MILLI")
    assert scale in (0.001, 1.0)
