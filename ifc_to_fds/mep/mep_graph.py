"""Source-qualified MEP relationships, placements and coverage."""

import numpy as np
import ifcopenshell.util.placement
from ifc_to_fds.core.canonical import MEPGraph, MEPSystem, MEPConnection, PortReference
from .classifier import classify_mep_element, MEP_TYPES


def safe_by_type(file, name):
    try:
        return file.by_type(name)
    except RuntimeError:
        return []


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
        category, critical = classify_mep_element(group.is_a(), name, name, predefined)
        system = systems.setdefault(
            gid,
            MEPSystem(
                system_id=gid,
                name=name,
                system_type=category,
                is_fire_safety_critical=critical,
            ),
        )
        for item in rel.RelatedObjects:
            e = by_step.get(item.id())
            if e and e.entity_key not in system.element_keys:
                system.element_keys.append(e.entity_key)
                system.element_global_ids.append(e.global_id)
                e.system_ids.append(gid)
                e.system_names.append(name)
    graph.systems = list(systems.values())
    owners = {}

    def register(port, owner):
        if port.id() in owners and owners[port.id()] != owner.id():
            graph.issues.append(f"Conflicting port owner: {key(port)}")
        owners[port.id()] = owner.id()

    for rel in safe_by_type(file, "IfcRelConnectsPortToElement"):
        register(rel.RelatingPort, rel.RelatedElement)
    for rel in safe_by_type(file, "IfcRelNests"):
        for child in rel.RelatedObjects:
            if child.is_a("IfcDistributionPort"):
                register(child, rel.RelatingObject)
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
        )
        owner.ports.append(ref)
        ports[port.id()] = ref
    connected = set()
    edges = set()
    for rel in safe_by_type(file, "IfcRelConnectsPorts"):
        a, b = ports.get(rel.RelatingPort.id()), ports.get(rel.RelatedPort.id())
        if not a or not b:
            graph.issues.append(f"Dangling connection: {key(rel)}")
            continue
        pair = tuple(sorted((a.port_key, b.port_key)))
        if pair in edges:
            continue
        edges.add(pair)
        a.connected_port_ids.append(b.port_key)
        b.connected_port_ids.append(a.port_key)
        distance = (
            float(
                np.linalg.norm(np.array(a.world_position) - np.array(b.world_position))
            )
            if a.world_position is not None and b.world_position is not None
            else 0.0
        )
        graph.connections.append(
            MEPConnection(
                connection_id=key(rel),
                source_element_id=a.owner_key,
                target_element_id=b.owner_key,
                source_port_id=a.port_key,
                target_port_id=b.port_key,
                relation_type="EXPLICIT_IFC",
                distance_meters=distance,
            )
        )
        connected.update((a.owner_key, b.owner_key))
    for e in model.elements:
        if e.ifc_type.upper() not in MEP_TYPES:
            continue
        system_types = [systems[s].system_type for s in e.system_ids]
        explicit = next((x for x in system_types if x != "OTHER"), "")
        category, _ = classify_mep_element(
            e.ifc_type, e.name, " ".join(e.system_names), e.predefined_type
        )
        e.mep_category = explicit or category
        e.classification_evidence = [
            f"IFC class: {e.ifc_type}",
            f"PredefinedType: {e.predefined_type}",
            *e.system_ids,
        ]
        if e.entity_key not in connected:
            graph.isolated_element_ids.append(e.entity_key)
    for category in (
        "VENTILATION",
        "SMOKE_EXTRACT",
        "FIRE_SUPPRESSION",
        "PLUMBING",
        "OTHER",
    ):
        members = [
            e
            for e in model.elements
            if e.ifc_type.upper() in MEP_TYPES and e.mep_category == category
        ]
        graph.coverage[category] = dict(
            source_count=len(members),
            ports=sum(len(e.ports) for e in members),
            connected=sum(e.entity_key in connected for e in members),
            entity_keys=[e.entity_key for e in members],
        )
    model.mep_graph = graph
    return model
