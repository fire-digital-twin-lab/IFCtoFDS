import os
from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.mep.classifier import classify_mep_element
from ifc_to_fds.mep.mep_graph import extract_mep_graph

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_mep_classifier():
    # Test ventilation classification
    cat, is_critical = classify_mep_element("IfcDuctSegment", "Supply Air Duct", {})
    assert cat == "VENTILATION"
    assert is_critical is False

    # Test smoke extract classification
    cat, is_critical = classify_mep_element("IfcFlowTerminal", "Smoke Exhaust Louver", {})
    assert cat == "SMOKE_EXTRACT"
    assert is_critical is True

    # Test fire suppression classification
    cat, is_critical = classify_mep_element("IfcFireSuppressionTerminal", "Sprinkler Head", {})
    assert cat == "FIRE_SUPPRESSION"
    assert is_critical is True


def test_duplex_mep_graph_extraction():
    duplex_path = os.path.join(REPO_ROOT, "examples", "IfcOpenShell-Duplex.ifc")
    model, ifc_file = extract_inventory(duplex_path)
    model = extract_mep_graph(model, ifc_file)

    # Duplex model contains distribution systems or flow elements
    assert model.mep_graph is not None
