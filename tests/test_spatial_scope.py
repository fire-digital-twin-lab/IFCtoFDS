import os
from ifc_to_fds.core.canonical import MappingStrategy
from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.mapping.scope import SpatialScope, apply_spatial_scope

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_spatial_scope_by_storey():
    fzk_path = os.path.join(REPO_ROOT, "examples", "AC20-FZK-Haus.ifc")
    model, _ = extract_inventory(fzk_path)

    assert len(model.elements) == 110

    # Scope to Erdgeschoss only
    scope = SpatialScope(storeys=["Erdgeschoss"])
    scoped_model = apply_spatial_scope(model, scope)

    # Ingestion remains 100% (no silent dropping of inventory)
    assert len(scoped_model.elements) == 110

    # Elements on Dachgeschoss must be marked EXCLUDED_APPROVED
    excluded_elements = [
        el for el in scoped_model.elements
        if el.mapping_strategy == MappingStrategy.EXCLUDED_APPROVED
    ]
    assert len(excluded_elements) > 0

    # Elements on Erdgeschoss must NOT be excluded
    erdgeschoss_elements = [
        el for el in scoped_model.elements
        if el.storey == "Erdgeschoss"
    ]
    for el in erdgeschoss_elements:
        assert el.mapping_strategy != MappingStrategy.EXCLUDED_APPROVED
