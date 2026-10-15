import os
from ifc_to_fds.core.inventory import extract_inventory

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_fzk_inventory_100_percent_ingestion():
    fzk_path = os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    model, ifc_file = extract_inventory(fzk_path)

    all_products = ifc_file.by_type("IfcProduct")
    opening_elements = ifc_file.by_type("IfcOpeningElement")

    # 127 total products, 17 openings (tracked on host walls), 110 physical elements
    assert len(all_products) == 127
    assert len(opening_elements) == 17
    assert len(model.elements) == len(all_products) - len(opening_elements)
    assert len(model.elements) == 110

    # Ensure SHA-256 hash was calculated
    assert model.source.file_hash_sha256 is not None
    assert len(model.source.file_hash_sha256) == 64

    # Ensure storeys were discovered
    assert "Erdgeschoss" in model.storeys
    assert "Dachgeschoss" in model.storeys

    # Ensure elements retain GlobalId and step_id
    guids = {el.global_id for el in model.elements}
    assert len(guids) == 110  # 100% unique GUIDs

    # Verify openings are mapped to host walls
    walls_with_openings = [el for el in model.elements if len(el.openings) > 0]
    total_tracked_openings = sum(len(el.openings) for el in model.elements)
    assert len(walls_with_openings) > 0
    assert total_tracked_openings == 17


def test_duplex_inventory_expanded_types():
    duplex_path = os.path.join(REPO_ROOT, "examples", "IfcOpenShell-Duplex.ifc")
    model, ifc_file = extract_inventory(duplex_path)

    all_products = ifc_file.by_type("IfcProduct")
    opening_elements = ifc_file.by_type("IfcOpeningElement")

    assert len(model.elements) == len(all_products) - len(opening_elements)
    assert len(model.elements) == 245
