"""IFC Source Inventory and Ingestion Engine.

Performs complete, non-lossy accounting of all IfcProduct entities, spatial
structures, property sets, and relationships in the source IFC model.
"""

import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
from ifc_to_fds.diagnostics import operation

from .canonical import (
    CanonicalElement,
    CanonicalModel,
    MappingStatus,
    MappingStrategy,
    OpeningReference,
    SourceMetadata,
    StoreyReference,
)
from .units import get_length_unit_scale
from .placement import extract_placement


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


def source_representations(product):
    """Small, non-tessellating representation provenance for source remediation."""
    def describe(rep, seen):
        result = dict(step_id=rep.id(), identifier=rep.RepresentationIdentifier,
                      representation_type=rep.RepresentationType)
        items = tuple(rep.Items or ())
        result["item_types"] = sorted({item.is_a() for item in items})
        result["item_count"] = len(items)
        result["item_step_ids"] = [item.id() for item in items[:32]]
        mappings = []
        for item in items:
            if not item.is_a("IfcMappedItem"):
                continue
            source = item.MappingSource
            nested = source.MappedRepresentation
            if nested.id() not in seen and len(seen) < 16:
                mappings.append(dict(map_step_id=source.id(),
                    representation=describe(nested, seen | {nested.id()})))
        if mappings:
            result["mapped_sources"] = mappings
        return result
    representation = getattr(product, "Representation", None)
    return [describe(rep, {rep.id()}) for rep in representation.Representations] if representation else []


@operation("IFC_PARSE")
def open_ifc(file_path):
    return ifcopenshell.open(file_path)


@operation("IFC_READ")
def extract_inventory(file_path: str) -> Tuple[CanonicalModel, Any]:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"IFC file not found: {file_path}")

    file_size = os.path.getsize(file_path)
    file_hash = compute_file_sha256(file_path)

    ifc_file = open_ifc(file_path)
    schema = ifc_file.schema
    unit_name, unit_scale = get_length_unit_scale(ifc_file)

    original_filename = os.path.basename(file_path)
    # Job uploads use safe local names; preserve the client filename as metadata.
    from pathlib import Path
    import json

    upload_names = Path(file_path).parent / "upload-names.json"
    if upload_names.is_file():
        names = json.loads(upload_names.read_text(encoding="utf-8"))
        original_filename = names.get(os.path.basename(file_path), original_filename)
    source_meta = SourceMetadata(
        source_id=file_hash,
        filename=original_filename,
        file_path=os.path.abspath(file_path),
        file_hash_sha256=file_hash,
        file_size_bytes=file_size,
        schema_version=schema,
        unit_length_name=unit_name,
        unit_scale_to_meters=unit_scale,
    )

    def ancestry(item):
        result = []
        seen = set()
        while item is not None and item.id() not in seen:
            seen.add(item.id())
            result.append(item)
            item = ifcopenshell.util.element.get_aggregate(item)
        return result

    def building_and_path(item):
        chain = ancestry(item)
        building = next((x for x in chain if x.is_a("IfcBuilding")), None)
        return (
            f"{file_hash}:{building.id()}" if building else None,
            [f"{file_hash}:{x.id()}" for x in chain],
        )

    storey_refs = []
    for s in ifc_file.by_type("IfcBuildingStorey"):
        elevation = None
        if s.ObjectPlacement:
            elevation = (
                float(
                    ifcopenshell.util.placement.get_local_placement(s.ObjectPlacement)[
                        2, 3
                    ]
                )
                * unit_scale
            )
        elif s.Elevation is not None:
            elevation = float(s.Elevation) * unit_scale
        storey_refs.append(
            StoreyReference(
                building_id=building_and_path(s)[0],
                spatial_ancestry=building_and_path(s)[1],
                storey_id=f"{file_hash}:{s.id()}",
                source_id=file_hash,
                name=s.Name or s.GlobalId,
                elevation_m=elevation,
            )
        )
    # Spatial storeys
    storeys: List[str] = [
        storey.Name or storey.GlobalId
        for storey in ifc_file.by_type("IfcBuildingStorey")
    ]

    elements: List[CanonicalElement] = []

    # Map opening elements to their fillings and hosts
    openings_by_host: Dict[int, List[OpeningReference]] = {}
    for rel in ifc_file.by_type("IfcRelVoidsElement"):
        host = rel.RelatingBuildingElement
        opening = rel.RelatedOpeningElement
        if not host or not opening:
            continue

        host_id = host.id()
        fillings = []
        for fill_rel in getattr(opening, "HasFillings", []):
            filling_el = getattr(fill_rel, "RelatedBuildingElement", None)
            if filling_el:
                fillings.append(filling_el.GlobalId)

        ref = OpeningReference(
            entity_key=f"{file_hash}:{opening.id()}",
            host_entity_key=f"{file_hash}:{host.id()}",
            void_relation_key=f"{file_hash}:{rel.id()}",
            filling_entity_keys=[
                f"{file_hash}:{r.RelatedBuildingElement.id()}"
                for r in getattr(opening, "HasFillings", ())
                if getattr(r, "RelatedBuildingElement", None) is not None
            ],
            filling_relation_keys=[
                f"{file_hash}:{r.id()}"
                for r in getattr(opening, "HasFillings", ())
                if getattr(r, "RelatedBuildingElement", None) is not None
            ],
            placement=extract_placement(opening, unit_scale),
            opening_global_id=opening.GlobalId,
            opening_step_id=opening.id(),
            opening_name=opening.Name or "Opening",
            opening_type=opening.is_a(),
            filling_global_ids=fillings,
        )
        openings_by_host.setdefault(host_id, []).append(ref)

    def _has_3d_body_representation(prod):
        rep = getattr(prod, "Representation", None)
        if not rep:
            return False
        if prod.is_a() in (
            "IfcGrid",
            "IfcGridAxis",
            "IfcPositioningElement",
            "IfcReferencingElement",
        ):
            return False
        return True

    # Ingest 100% of IfcProduct entities
    all_products: List[Any] = list(ifc_file.by_type("IfcProduct"))
    for prod in all_products:
        prod_any: Any = prod
        guid = prod.GlobalId
        step_id = prod.id()
        ifc_type = prod.is_a()
        name = prod.Name or f"{ifc_type}_{step_id}"
        tag = getattr(prod, "Tag", None)
        storey = find_containing_storey(prod)
        psets = ifcopenshell.util.element.get_psets(prod_any)
        container = ifcopenshell.util.element.get_container(prod_any)
        if container is None:
            for ancestor in ancestry(prod):
                parent_container = ifcopenshell.util.element.get_container(ancestor)
                if parent_container:
                    container = parent_container
                    break
        if prod.is_a("IfcOpeningElement"):
            voids = getattr(prod, "VoidsElements", ())
            if voids:
                container = ifcopenshell.util.element.get_container(
                    voids[0].RelatingBuildingElement
                )
        if container and container.is_a("IfcBuildingStorey"):
            storey = container.Name or container.GlobalId
        openings = openings_by_host.get(step_id, [])

        parts = ifcopenshell.util.element.get_parts(prod_any) if not prod.is_a("IfcOpeningElement") else []
        is_assembly_without_geom = len(parts) > 0 and getattr(prod, "Representation", None) is None

        has_geom = _has_3d_body_representation(prod)

        t_prod = ifcopenshell.util.element.get_type(prod_any)
        elem = CanonicalElement(
            placement=extract_placement(prod, source_meta.unit_scale_to_meters),
            building_id=building_and_path(container)[0] if container else None,
            spatial_ancestry=building_and_path(container)[1] if container else [],
            type_class=(
                t_prod.is_a()
                if t_prod is not None
                else None
            ),
            source_id=file_hash,
            entity_key=f"{file_hash}:{step_id}",
            storey_id=f"{file_hash}:{container.id()}"
            if container and container.is_a("IfcBuildingStorey")
            else None,
            role="OPENING"
            if prod.is_a("IfcOpeningElement")
            else "PORT"
            if prod.is_a("IfcDistributionPort")
            else "SPATIAL"
            if (
                is_assembly_without_geom
                or prod.is_a() in (
                    "IfcSite",
                    "IfcBuilding",
                    "IfcBuildingStorey",
                    "IfcSpace",
                    "IfcAnnotation",
                    "IfcVirtualElement",
                    "IfcGrid",
                    "IfcGridAxis",
                    "IfcPositioningElement",
                    "IfcReferencingElement",
                )
            )
            else "PHYSICAL",
            predefined_type=ifcopenshell.util.element.get_predefined_type(prod_any),
            global_id=guid,
            step_id=step_id,
            ifc_type=ifc_type,
            name=name,
            tag=str(tag) if tag is not None else None,
            storey=storey,
            property_sets=psets,
            has_3d_geometry=has_geom,
            source_representations=source_representations(prod),
            openings=openings,
            mapping_status=MappingStatus.INCONCLUSIVE
            if has_geom
            else MappingStatus.SEMANTIC_ONLY,
            mapping_strategy=MappingStrategy.GEOM
            if has_geom
            else MappingStrategy.SEMANTIC_ONLY,
        )
        elements.append(elem)

    canonical = CanonicalModel(
        source=source_meta,
        sources=[source_meta],
        elements=elements,
        storeys=storeys,
        storey_references=storey_refs,
    )
    return canonical, ifc_file


Tuple_Canonical_and_File = Any
