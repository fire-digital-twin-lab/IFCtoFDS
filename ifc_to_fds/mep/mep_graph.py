"""MEP Topology Graph Extractor.

Extracts systems, ports, explicit connections, and topological relationships
from IFC distribution models according to IFC2X3 and IFC4 schemas.
"""

from typing import Dict, List, Set, Any
import ifcopenshell

from ifc_to_fds.core.canonical import (
    CanonicalModel,
    MEPConnection,
    MEPGraph,
    MEPSystem,
    PortReference,
)
from .classifier import classify_mep_element


def extract_mep_graph(canonical_model: CanonicalModel, ifc_file: ifcopenshell.file) -> CanonicalModel:
    element_by_guid = {elem.global_id: elem for elem in canonical_model.elements}
    element_by_step_id = {elem.step_id: elem for elem in canonical_model.elements}

    # 1. Systems extraction (IfcSystem / IfcDistributionSystem)
    systems: List[MEPSystem] = []
    system_assignment_rels = ifc_file.by_type("IfcRelAssignsToGroup")

    for rel in system_assignment_rels:
        group = getattr(rel, "RelatingGroup", None)
        if not group:
            continue
        if not (group.is_a("IfcSystem") or group.is_a("IfcDistributionSystem")):
            continue

        sys_guid = group.GlobalId
        sys_name = getattr(group, "Name", None) or f"System_{group.id()}"
        members: List[str] = []

        for obj in getattr(rel, "RelatedObjects", []):
            if obj.GlobalId in element_by_guid:
                members.append(obj.GlobalId)
                elem = element_by_guid[obj.GlobalId]
                elem.system_ids.append(sys_guid)
                elem.system_names.append(sys_name)

        sys_type, is_critical = classify_mep_element(group.is_a(), sys_name, sys_name)
        systems.append(
            MEPSystem(
                system_id=sys_guid,
                name=sys_name,
                system_type=sys_type,
                element_global_ids=members,
                is_fire_safety_critical=is_critical,
            )
        )

    # 2. Port extraction
    port_to_element_step: Dict[int, int] = {}

    # IFC2X3: IfcRelConnectsPortToElement
    for rel in ifc_file.by_type("IfcRelConnectsPortToElement"):
        port = getattr(rel, "RelatingPort", None)
        elem = getattr(rel, "RelatedElement", None)
        if port and elem:
            port_to_element_step[port.id()] = elem.id()

    # IFC4: IfcRelNests
    for rel in ifc_file.by_type("IfcRelNests"):
        parent = getattr(rel, "RelatingObject", None)
        for child in getattr(rel, "RelatedObjects", []):
            if child and child.is_a("IfcDistributionPort") and parent:
                port_to_element_step[child.id()] = parent.id()

    # Register ports on CanonicalElements
    ports_by_id: Dict[int, Any] = {}
    for port in ifc_file.by_type("IfcDistributionPort"):
        ports_by_id[port.id()] = port
        parent_step_id = port_to_element_step.get(port.id())
        if parent_step_id and parent_step_id in element_by_step_id:
            parent_elem = element_by_step_id[parent_step_id]
            port_ref = PortReference(
                port_global_id=port.GlobalId,
                port_step_id=port.id(),
                name=getattr(port, "Name", None),
                flow_direction=str(getattr(port, "FlowDirection", "NOTDEFINED")),
            )
            parent_elem.ports.append(port_ref)

    # 3. Connection extraction (IfcRelConnectsPorts)
    connections: List[MEPConnection] = []
    connected_elements: Set[str] = set()

    for idx, rel in enumerate(ifc_file.by_type("IfcRelConnectsPorts")):
        port_a = getattr(rel, "RelatingPort", None)
        port_b = getattr(rel, "RelatedPort", None)
        if not port_a or not port_b:
            continue

        elem_a_id = port_to_element_step.get(port_a.id())
        elem_b_id = port_to_element_step.get(port_b.id())

        elem_a = element_by_step_id.get(elem_a_id) if elem_a_id else None
        elem_b = element_by_step_id.get(elem_b_id) if elem_b_id else None

        if elem_a and elem_b:
            conn = MEPConnection(
                connection_id=f"conn_{idx}_{port_a.id()}_{port_b.id()}",
                source_element_id=elem_a.global_id,
                source_port_id=port_a.GlobalId,
                target_element_id=elem_b.global_id,
                target_port_id=port_b.GlobalId,
                relation_type="EXPLICIT_IFC",
                distance_meters=0.0,
            )
            connections.append(conn)
            connected_elements.add(elem_a.global_id)
            connected_elements.add(elem_b.global_id)

    # Identify isolated MEP elements (flow segments/fittings with no recorded connection)
    isolated_ids: List[str] = []
    for elem in canonical_model.elements:
        if "FLOW" in elem.ifc_type.upper() or "DUCT" in elem.ifc_type.upper() or "PIPE" in elem.ifc_type.upper():
            if elem.global_id not in connected_elements:
                isolated_ids.append(elem.global_id)

    canonical_model.mep_graph = MEPGraph(
        systems=systems,
        connections=connections,
        isolated_element_ids=isolated_ids,
    )

    return canonical_model
