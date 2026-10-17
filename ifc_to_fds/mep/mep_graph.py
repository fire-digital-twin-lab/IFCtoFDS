"""Source-qualified MEP relationships, placements and coverage."""

import numpy as np
import ifcopenshell.util.placement
import ifcopenshell.util.element
from ifc_to_fds.core.canonical import MEPGraph, MEPSystem, MEPConnection, PortReference
from .classifier import classify_mep_element, MEP_TYPES
from ifc_to_fds.diagnostics import operation


def safe_by_type(file, name):
    try:
        return file.by_type(name)
    except RuntimeError:
        return []


@operation("MEP_EXTRACTION")
def extract_mep_graph(model, file):
    by_step = {e.step_id: e for e in model.elements}
    source = model.source
    prefix = source.source_id

    def key(item):
        return f"{prefix}:{item.id()}"

    graph = MEPGraph()
    for e in model.elements:
        e.ports = []
        e.system_ids = []
        e.system_names = []
    systems = {}
    for rel in safe_by_type(file, "IfcRelAssignsToGroup"):
        group = rel.RelatingGroup
        if not group.is_a("IfcSystem"):
            continue
        gid = key(group)
        name = group.Name or gid
        predefined = str(getattr(group, "PredefinedType", "") or "")
        object_type = str(getattr(group, "ObjectType", "") or "")
        psets = ifcopenshell.util.element.get_psets(group)
        category, critical = classify_mep_element(
            group.is_a(),
            name,
            name,
            predefined,
            property_sets=psets,
            object_type=object_type,
        )
        system = systems.setdefault(
            gid,
            MEPSystem(
                ifc_type=group.is_a(),
                object_type=object_type,
                predefined_type=predefined,
                description=str(getattr(group, "Description", "") or ""),
                property_sets=psets,
                classifications=[
                    {
                        "relation_key": key(association),
                        "ifc_type": association.RelatingClassification.is_a(),
                        **{
                            attr: str(
                                getattr(association.RelatingClassification, attr, "")
                                or ""
                            )
                            for attr in (
                                "Identification",
                                "ItemReference",
                                "Name",
                                "Location",
                            )
                        },
                    }
                    for association in getattr(group, "HasAssociations", ())
                    if association.is_a("IfcRelAssociatesClassification")
                ],
                classification_evidence=[
                    f"IFC system class: {group.is_a()}",
                    f"PredefinedType: {predefined}",
                    f"ObjectType: {object_type}",
                    "Exact declared ObjectType vocabulary v1; free Name is not classification evidence; unknown/conflicting values remain UNRESOLVED",
                ],
                system_id=gid,
                name=name,
                system_type=category,
                is_fire_safety_critical=critical,
            ),
        )
        if key(rel) not in system.assignment_relation_keys:
            system.assignment_relation_keys.append(key(rel))
        for item in rel.RelatedObjects:
            e = by_step.get(item.id())
            if e and e.entity_key not in system.element_keys:
                system.element_keys.append(e.entity_key)
                system.element_global_ids.append(e.global_id)
                e.system_ids.append(gid)
                e.system_names.append(name)
    graph.systems = list(systems.values())
    owners = {}
    ownership_rel_keys = {}
    ownership_rel_types = {}

    def register(port, owner, rel):
        if port.id() in owners and owners[port.id()] != owner.id():
            graph.issues.append(f"Conflicting port owner: {key(port)}")
        owners[port.id()] = owner.id()
        ownership_rel_keys.setdefault(port.id(), []).append(key(rel))
        ownership_rel_types[port.id()] = rel.is_a()

    for rel in safe_by_type(file, "IfcRelConnectsPortToElement"):
        register(rel.RelatingPort, rel.RelatedElement, rel)
    for rel in safe_by_type(file, "IfcRelNests"):
        for child in rel.RelatedObjects:
            if child.is_a("IfcDistributionPort"):
                register(child, rel.RelatingObject, rel)
    ports = {}
    for port in safe_by_type(file, "IfcDistributionPort"):
        owner = by_step.get(owners.get(port.id()))
        if not owner:
            graph.issues.append(f"Orphan port: {key(port)}")
            continue
        local = world = None
        if port.ObjectPlacement:
            placement = ifcopenshell.util.placement.get_local_placement(
                port.ObjectPlacement
            )
            world = placement[:3, 3] * source.unit_scale_to_meters
            owner_ifc = file.by_id(owner.step_id)
            owner_matrix = ifcopenshell.util.placement.get_local_placement(
                owner_ifc.ObjectPlacement
            )
            local = (np.linalg.inv(owner_matrix) @ np.r_[placement[:3, 3], 1.0])[
                :3
            ] * source.unit_scale_to_meters
        else:
            graph.issues.append(f"Port placement missing: {key(port)}")
        ref = PortReference(
            port_key=key(port),
            port_global_id=port.GlobalId,
            port_step_id=port.id(),
            owner_key=owner.entity_key,
            name=port.Name,
            flow_direction=str(port.FlowDirection),
            local_position=local.tolist() if local is not None else None,
            world_position=world.tolist() if world is not None else None,
            ownership_relation_keys=ownership_rel_keys.get(port.id(), []),
            ownership_relation_type=ownership_rel_types.get(port.id()),
        )
        owner.ports.append(ref)
        ports[port.id()] = ref
    connected = set()
    edges = {}
    for rel in safe_by_type(file, "IfcRelConnectsPorts"):
        a, b = ports.get(rel.RelatingPort.id()), ports.get(rel.RelatedPort.id())
        if not a or not b:
            graph.issues.append(f"Dangling connection: {key(rel)}")
            continue
        pair = tuple(sorted((a.port_key, b.port_key)))
        if pair in edges:
            edges[pair].source_relation_keys.append(key(rel))
            continue
        a.connected_port_ids.append(b.port_key)
        b.connected_port_ids.append(a.port_key)
        distance = (
            float(
                np.linalg.norm(np.array(a.world_position) - np.array(b.world_position))
            )
            if a.world_position is not None and b.world_position is not None
            else None
        )
        graph.connections.append(
            MEPConnection(
                source_relation_keys=[key(rel)],
                connection_id=key(rel),
                source_element_id=a.owner_key,
                target_element_id=b.owner_key,
                source_port_id=a.port_key,
                target_port_id=b.port_key,
                relation_type="EXPLICIT_IFC",
                distance_meters=distance,
            )
        )
        edges[pair] = graph.connections[-1]
        connected.update((a.owner_key, b.owner_key))
    for e in model.elements:
        if e.role != "PHYSICAL":
            continue
        has_mep_properties = any(
            isinstance(props, dict)
            and any(
                k.replace(" ", "").lower()
                in ("systemtype", "systemclassification", "servicetype")
                for k in props
            )
            for props in (e.property_sets or {}).values()
        )
        is_mep = (
            e.ifc_type.upper() in MEP_TYPES
            or (e.type_class or "").upper().removesuffix("TYPE") in MEP_TYPES
            or bool(e.system_ids)
            or bool(e.ports)
            or has_mep_properties
        )
        if not is_mep:
            continue
        system_types = [systems[s].system_type for s in e.system_ids]
        category, _ = classify_mep_element(
            e.ifc_type,
            e.name,
            " ".join(e.system_names),
            e.predefined_type,
            e.type_class,
            e.property_sets,
            system_types,
        )
        e.mep_category = category
        e.classification_evidence = [
            f"IFC class: {e.ifc_type}",
            f"IFC type class: {e.type_class}",
            f"PredefinedType: {e.predefined_type}",
            *e.system_ids,
            f"Classification: {category}; names are unconfirmed hints: {e.name}; {'; '.join(e.system_names)}",
        ]
        if e.entity_key not in connected:
            graph.isolated_element_ids.append(e.entity_key)
    for category in (
        "VENTILATION",
        "SMOKE_EXTRACT",
        "FIRE_SUPPRESSION",
        "PLUMBING",
        "OTHER",
        "UNRESOLVED",
    ):
        members = [
            e
            for e in model.elements
            if e.classification_evidence and e.mep_category == category
        ]
        graph.coverage[category] = dict(
            source_count=len(members),
            ports=sum(len(e.ports) for e in members),
            connected=sum(e.entity_key in connected for e in members),
            entity_keys=[e.entity_key for e in members],
            assigned_to_systems=sum(bool(e.system_ids) for e in members),
            elements_with_ports=sum(bool(e.ports) for e in members),
            connected_ports=sum(
                bool(p.connected_port_ids) for e in members for p in e.ports
            ),
            isolated_ports=sum(
                not p.connected_port_ids for e in members for p in e.ports
            ),
            unsupported_elements=[
                e.entity_key for e in members if e.geometry_status.value == "FAILED"
            ],
        )
    graph.coverage["source_relationships"] = dict(
        distribution_ports=len(safe_by_type(file, "IfcDistributionPort")),
        explicit_port_relations=len(safe_by_type(file, "IfcRelConnectsPorts")),
        accounted_edge_relations=sum(
            len(c.source_relation_keys) for c in graph.connections
        ),
        unresolved_system_keys=[
            s.system_id for s in graph.systems if s.system_type == "UNRESOLVED"
        ],
        orphan_port_keys=[
            key(p)
            for p in safe_by_type(file, "IfcDistributionPort")
            if p.id() not in ports
        ],
    )
    model.mep_graph = graph
    return model
