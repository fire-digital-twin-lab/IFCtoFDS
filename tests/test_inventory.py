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
    assert len(model.elements) == len(all_products)
    assert len(model.elements) == 127

    # Ensure SHA-256 hash was calculated
    assert model.source.file_hash_sha256 is not None
    assert len(model.source.file_hash_sha256) == 64

    # Ensure storeys were discovered
    assert "Erdgeschoss" in model.storeys
    assert "Dachgeschoss" in model.storeys

    # Ensure elements retain GlobalId and step_id
    guids = {el.global_id for el in model.elements}
    assert len(guids) == 127  # 100% unique GUIDs

    # Verify openings are mapped to host walls
    walls_with_openings = [el for el in model.elements if len(el.openings) > 0]
    total_tracked_openings = sum(len(el.openings) for el in model.elements)
    assert len(walls_with_openings) > 0
    assert total_tracked_openings == 17


def test_duplex_inventory_expanded_types():
    duplex_path = os.path.join(REPO_ROOT, "examples", "IfcOpenShell-Duplex.ifc")
    model, ifc_file = extract_inventory(duplex_path)

    all_products = ifc_file.by_type("IfcProduct")

    assert len(model.elements) == len(all_products)
    assert len(model.elements) == 295


def test_nonphysical_products_remain_accounted():
    model, source = extract_inventory(
        os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    )
    assert {e.step_id for e in model.elements} == {
        e.id() for e in source.by_type("IfcProduct")
    }
    assert sum(e.role == "OPENING" for e in model.elements) == 17
    assert len({e.entity_key for e in model.elements}) == len(model.elements)


def test_dangling_opening_filling_does_not_crash(tiny_ifc, tmp_path):
    import ifcopenshell.api.root

    path, file, wall = tiny_ifc
    opening = ifcopenshell.api.root.create_entity(
        file, ifc_class="IfcOpeningElement", name="Void with dangling fill"
    )
    opening.ObjectPlacement = wall.ObjectPlacement
    file.create_entity(
        "IfcRelVoidsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingBuildingElement=wall,
        RelatedOpeningElement=opening,
    )
    # Dangling filling relationship where RelatedBuildingElement is None
    file.create_entity(
        "IfcRelFillsElement",
        GlobalId=ifcopenshell.guid.new(),
        RelatingOpeningElement=opening,
        RelatedBuildingElement=None,
    )
    dangling_path = tmp_path / "dangling.ifc"
    file.write(str(dangling_path))
    model, _ = extract_inventory(str(dangling_path))
    host_wall = next(e for e in model.elements if e.step_id == wall.id())
    assert len(host_wall.openings) == 1
    assert host_wall.openings[0].filling_entity_keys == []

