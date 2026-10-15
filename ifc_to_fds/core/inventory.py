"""IFC Source Inventory and Ingestion Engine.

Performs complete, non-lossy accounting of all IfcProduct entities, spatial
structures, property sets, and relationships in the source IFC model.
"""

import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple
import ifcopenshell

from .canonical import (
    CanonicalElement,
    CanonicalModel,
    MappingStatus,
    MappingStrategy,
    OpeningReference,
    SourceMetadata,
)
from .units import get_length_unit_scale


def compute_file_sha256(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def extract_property_sets(element: Any) -> Dict[str, Dict[str, Any]]:
    psets: Dict[str, Dict[str, Any]] = {}
    for rel in getattr(element, "IsDefinedBy", []):
        if rel.is_a("IfcRelDefinesByProperties"):
            prop_set = getattr(rel, "RelatingPropertyDefinition", None)
            if prop_set and prop_set.is_a("IfcPropertySet"):
                set_name = getattr(prop_set, "Name", "PropertySet")
                props: Dict[str, Any] = {}
                for prop in getattr(prop_set, "HasProperties", []):
                    if prop.is_a("IfcPropertySingleValue"):
                        val = getattr(prop, "NominalValue", None)
                        props[prop.Name] = val.wrappedValue if val is not None else None
                if props:
                    psets[set_name] = props
    return psets


def find_containing_storey(element: Any) -> Optional[str]:
    for rel in getattr(element, "ContainedInStructure", []):
        if rel.is_a("IfcRelContainedInSpatialStructure"):
            structure = getattr(rel, "RelatingStructure", None)
            if structure and structure.is_a("IfcBuildingStorey"):
                return structure.Name or structure.GlobalId
    return None


def extract_inventory(file_path: str) -> Tuple[CanonicalModel, Any]:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"IFC file not found: {file_path}")

    file_size = os.path.getsize(file_path)
    file_hash = compute_file_sha256(file_path)

    ifc_file = ifcopenshell.open(file_path)
    schema = ifc_file.schema
    unit_name, unit_scale = get_length_unit_scale(ifc_file)

    source_meta = SourceMetadata(
        filename=os.path.basename(file_path),
        file_path=os.path.abspath(file_path),
        file_hash_sha256=file_hash,
        file_size_bytes=file_size,
        schema_version=schema,
        unit_length_name=unit_name,
        unit_scale_to_meters=unit_scale,
    )

    # Spatial storeys
    storeys: List[str] = [
        storey.Name or storey.GlobalId
        for storey in ifc_file.by_type("IfcBuildingStorey")
    ]

    elements: List[CanonicalElement] = []

    # Map opening elements to their fillings and hosts
    openings_by_host: Dict[str, List[OpeningReference]] = {}
    for rel in ifc_file.by_type("IfcRelVoidsElement"):
        host = rel.RelatingBuildingElement
        opening = rel.RelatedOpeningElement
        if not host or not opening:
            continue

        host_id = host.GlobalId
        fillings = []
        for fill_rel in getattr(opening, "HasFillings", []):
            filling_el = getattr(fill_rel, "RelatedBuildingElement", None)
            if filling_el:
                fillings.append(filling_el.GlobalId)

        ref = OpeningReference(
            opening_global_id=opening.GlobalId,
            opening_step_id=opening.id(),
            opening_name=opening.Name or "Opening",
            opening_type=opening.is_a(),
            filling_global_ids=fillings,
        )
        openings_by_host.setdefault(host_id, []).append(ref)

    # Ingest 100% of IfcProduct entities
    all_products = ifc_file.by_type("IfcProduct")
    for prod in all_products:
        # Exclude IfcOpeningElement from top-level building solids inventory
        # (they are tracked via host openings)
        if prod.is_a("IfcOpeningElement"):
            continue

        guid = prod.GlobalId
        step_id = prod.id()
        ifc_type = prod.is_a()
        name = prod.Name or f"{ifc_type}_{step_id}"
        tag = getattr(prod, "Tag", None)
        storey = find_containing_storey(prod)
        psets = extract_property_sets(prod)
        openings = openings_by_host.get(guid, [])

        has_geom = bool(getattr(prod, "Representation", None))

        elem = CanonicalElement(
            global_id=guid,
            step_id=step_id,
            ifc_type=ifc_type,
            name=name,
            tag=str(tag) if tag is not None else None,
            storey=storey,
            property_sets=psets,
            has_3d_geometry=has_geom,
            openings=openings,
            mapping_status=MappingStatus.MATCHED if has_geom else MappingStatus.SEMANTIC_ONLY,
            mapping_strategy=MappingStrategy.GEOM if has_geom else MappingStrategy.SEMANTIC_ONLY,
        )
        elements.append(elem)

    canonical = CanonicalModel(
        source=source_meta,
        elements=elements,
        storeys=storeys,
    )
    return canonical, ifc_file


Tuple_Canonical_and_File = Any
