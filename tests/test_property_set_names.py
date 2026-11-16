"""Unnamed source properties survive the canonical inventory without collisions."""

import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.type
import ifcopenshell.util.element
import pytest

from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.mep.mep_graph import extract_mep_graph


def attach(file, wall, definition):
    file.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[wall],
        RelatingPropertyDefinition=definition,
    )


def inventory_wall(path, file, wall):
    file.write(str(path))
    model, source = extract_inventory(str(path))
    return model, source, next(e for e in model.elements if e.step_id == wall.id())


@pytest.mark.parametrize("named_first", [False, True])
def test_unnamed_sets_and_properties_survive_inventory(tiny_ifc, named_first):
    path, file, wall = tiny_ifc
    named = file.create_entity(
        "IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
        Name="(unnamed property set)",
        HasProperties=[file.create_entity(
            "IfcPropertySingleValue", Name="Unchanged",
            NominalValue=file.create_entity("IfcLabel", "real set"),
        )],
    )
    quantity = file.create_entity(
        "IfcElementQuantity", GlobalId=ifcopenshell.guid.new(),
        Quantities=[file.create_entity("IfcQuantityLength", Name="Length", LengthValue=2.0)],
    )
    unnamed = file.create_entity(
        "IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
        HasProperties=[
            file.create_entity("IfcPropertySingleValue", Name="(unnamed property)",
                               NominalValue=file.create_entity("IfcLabel", "real property")),
            file.create_entity("IfcPropertySingleValue",
                               NominalValue=file.create_entity("IfcLabel", "first")),
            file.create_entity("IfcPropertySingleValue",
                               NominalValue=file.create_entity("IfcLabel", "second")),
            file.create_entity("IfcPropertySingleValue", Name="SystemClassification",
                               NominalValue=file.create_entity("IfcLabel", "FIRE_SUPPRESSION")),
        ],
    )
    definitions = [named, quantity, unnamed] if named_first else [quantity, unnamed, named]
    for definition in definitions:
        attach(file, wall, definition)

    model, source, element = inventory_wall(path, file, wall)
    sets = element.property_sets
    assert len(sets) == 3
    assert all(isinstance(name, str) for name in sets)
    assert sets["(unnamed property set)"] == {"Unchanged": "real set", "id": named.id()}
    quantities = next(props for props in sets.values() if props["id"] == quantity.id())
    assert quantities["Length"] == 2.0
    properties = next(props for props in sets.values() if props["id"] == unnamed.id())
    assert properties["(unnamed property)"] == "real property"
    assert {v for k, v in properties.items() if k.startswith("(unnamed property)")} == {
        "real property", "first", "second",
    }
    assert all(isinstance(name, str) for name in properties)
    again, _, repeated = inventory_wall(path, file, wall)
    assert repeated.property_sets == sets
    extract_mep_graph(model, source)
    assert element.mep_category == "FIRE_SUPPRESSION"
    assert next(e for e in again.elements if e.step_id == wall.id()).property_sets == sets


def test_named_properties_keep_ifcopenshell_inheritance(tiny_ifc):
    path, file, wall = tiny_ifc
    wall_type = ifcopenshell.api.root.create_entity(file, ifc_class="IfcWallType")
    ifcopenshell.api.type.assign_type(file, related_objects=[wall], relating_type=wall_type)
    inherited = ifcopenshell.api.pset.add_pset(file, product=wall_type, name="Pset_Test")
    ifcopenshell.api.pset.edit_pset(file, pset=inherited, properties={"Common": "type", "OnlyType": 1})
    occurrence = ifcopenshell.api.pset.add_pset(file, product=wall, name="Pset_Test")
    ifcopenshell.api.pset.edit_pset(file, pset=occurrence, properties={"Common": "occurrence"})
    expected = ifcopenshell.util.element.get_psets(wall)
    _, _, element = inventory_wall(path, file, wall)
    assert element.property_sets == expected
    assert element.property_sets["Pset_Test"]["Common"] == "occurrence"
    assert element.property_sets["Pset_Test"]["OnlyType"] == 1


def test_inherited_unnamed_property_does_not_overwrite_real_name(tiny_ifc):
    path, file, wall = tiny_ifc
    wall_type = ifcopenshell.api.root.create_entity(file, ifc_class="IfcWallType")
    ifcopenshell.api.type.assign_type(file, related_objects=[wall], relating_type=wall_type)
    inherited = ifcopenshell.api.pset.add_pset(file, product=wall_type, name="Pset_Test")
    inherited.HasProperties = [file.create_entity(
        "IfcPropertySingleValue", NominalValue=file.create_entity("IfcLabel", "inherited"),
    )]
    occurrence = ifcopenshell.api.pset.add_pset(file, product=wall, name="Pset_Test")
    ifcopenshell.api.pset.edit_pset(
        file, pset=occurrence, properties={"(unnamed property)": "real name"},
    )
    _, _, element = inventory_wall(path, file, wall)
    properties = element.property_sets["Pset_Test"]
    assert properties["(unnamed property)"] == "real name"
    assert "inherited" in properties.values()


def test_unnamed_property_set_of_a_system_group_does_not_stop_the_mep_graph(tiny_ifc):
    path, file, wall = tiny_ifc
    system = file.create_entity("IfcSystem", GlobalId=ifcopenshell.guid.new(), Name="Sprinkler loop")
    file.create_entity("IfcRelAssignsToGroup", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[wall], RelatingGroup=system)
    attach(file, system, file.create_entity(
        "IfcPropertySet", GlobalId=ifcopenshell.guid.new(),
        HasProperties=[file.create_entity("IfcPropertySingleValue", Name="Kind", NominalValue=file.create_entity("IfcLabel", "sprinkler"))],
    ))
    model, source, _ = inventory_wall(path, file, wall)
    extract_mep_graph(model, source)
    assert model.mep_graph.systems
    assert all(isinstance(name, str) for group in model.mep_graph.systems for name in group.property_sets)
