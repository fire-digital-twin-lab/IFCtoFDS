"""Compile explicit IFC port topology and reviewed SI parameters into HVAC intent."""

import hashlib
import math
from ifc_to_fds.domain.mep.hvac import HvacDuct, HvacNetworkPlan, HvacNode, JunctionSpec, hvac_spec
from ifc_to_fds.domain.mapping.enums import MappingStrategy
from ifc_to_fds.domain.scope import ScopeDecision

PORT_POSITION_TOLERANCE_M = 0.001
SEGMENT_TYPES = ("IFCDUCTSEGMENT", "IFCFLOWSEGMENT")
FITTING_TYPES = ("IFCDUCTFITTING", "IFCFLOWFITTING")
FAN_TYPES = ("IFCFAN",)


def build_hvac_network(model):
    selected = [e for e in model.elements if e.mapping_strategy == MappingStrategy.HVAC
                and e.scope_decision in (ScopeDecision.IN_SCOPE, ScopeDecision.BOUNDARY_RETAINED)]
    if not selected:
        return HvacNetworkPlan()
    ports, owners, specs, junctions = {}, {}, {}, {}
    for e in selected:
        declared_type = (e.type_class or e.ifc_type).upper().removesuffix("TYPE")
        if declared_type not in SEGMENT_TYPES + FITTING_TYPES + FAN_TYPES or e.mep_category not in ("VENTILATION", "SMOKE_EXTRACT"):
            raise ValueError(f"HVAC requires a ventilation duct segment, two-port fitting or fixed-flow fan: {e.entity_key}")
        if e.decision.get("action") != "HVAC" or not e.decision.get("hvac"):
            raise ValueError(f"HVAC requires reviewed duct parameters and endpoint boundaries: {e.entity_key}")
        spec = hvac_spec(e.decision["hvac"])
        if isinstance(spec, JunctionSpec):
            if declared_type not in FITTING_TYPES or not 3 <= len(e.ports) <= 10:
                raise ValueError(f"HVAC junction losses belong to a fitting with three to ten ports: {e.entity_key}")
            junctions[e.entity_key] = spec
        else:
            specs[e.entity_key] = spec
            if len(e.ports) != 2:
                raise ValueError(f"HVAC duct requires exactly two source ports; a tee, wye or take-off needs reviewed junction losses: {e.entity_key}")
            if declared_type in FITTING_TYPES and (spec.loss is None or spec.length_m is None):
                raise ValueError(f"HVAC fitting needs reviewed loss coefficients and centreline length; the port chord is not its length: {e.entity_key}")
            directions = {(getattr(p, "flow_direction", None) or "").upper() for p in e.ports}
            if declared_type in FITTING_TYPES and spec.loss[0] != spec.loss[1] and directions != {"SINK", "SOURCE"}:
                raise ValueError(f"HVAC fitting with different forward/reverse losses needs SINK/SOURCE port directions: {e.entity_key}")
            if declared_type in FAN_TYPES:
                if spec.volume_flow_m3_s is None or directions != {"SINK", "SOURCE"}:
                    raise ValueError(f"HVAC fan needs a reviewed volume flow and SINK/SOURCE port directions; direction is never inferred: {e.entity_key}")
        for p in e.ports:
            if not p.port_key or p.port_key in ports or p.world_position is None or len(p.world_position) != 3 or not all(math.isfinite(x) for x in p.world_position):
                raise ValueError(f"HVAC requires unique source port keys and finite world positions: {e.entity_key}")
            ports[p.port_key], owners[p.port_key] = p, e.entity_key
        own = {p.port_key for p in e.ports}
        if e.entity_key in junctions:
            named = {x for loss in junctions[e.entity_key].losses for x in (loss.from_port, loss.to_port)}
            if named - own:
                raise ValueError(f"Unknown port in HVAC junction losses: {e.entity_key}")
        elif set(specs[e.entity_key].endpoints) - own:
            raise ValueError(f"Unknown endpoint port in HVAC configuration: {e.entity_key}")
    parent = {key: key for key in ports}

    def find(key):
        while key != parent[key]:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for edge in model.mep_graph.connections:
        a, b = edge.source_port_id, edge.target_port_id
        if a in ports and b in ports:
            if edge.relation_type != "EXPLICIT_IFC":
                raise ValueError("HVAC topology requires explicit IFC port relationships")
            if math.dist(ports[a].world_position, ports[b].world_position) > PORT_POSITION_TOLERANCE_M:
                raise ValueError("Connected HVAC ports disagree in world position")
            parent[find(b)] = find(a)
    for entity_key in junctions:  # all ports of a junction are one FDS node
        own = [k for k in ports if owners[k] == entity_key]
        for key in own[1:]:
            parent[find(key)] = find(own[0])
    groups = {}
    for key in sorted(ports):
        groups.setdefault(find(key), []).append(key)
    nodes, port_node = [], {}
    duct_ids = {e.entity_key: "D_" + hashlib.sha256(e.entity_key.encode()).hexdigest()[:20] for e in selected if e.entity_key in specs}
    for keys in groups.values():
        node_id = "N_" + hashlib.sha256("|".join(keys).encode()).hexdigest()[:20]
        here = sorted({owners[k] for k in keys} & junctions.keys())
        if len(here) > 1:
            raise ValueError("Adjacent HVAC junctions would share one node; model a duct between them")
        boundaries = [specs[owners[k]].endpoints[k] for k in keys if owners[k] in specs and k in specs[owners[k]].endpoints]
        attached = sorted({duct_ids[owners[k]] for k in keys if owners[k] in specs})
        if len(attached) == 1 and len(keys) > 1:
            raise ValueError("HVAC duct cannot connect to itself")
        if len(attached) == 1 and len(boundaries) != 1:
            raise ValueError(f"Unconfigured HVAC endpoint (including scope cuts): {keys}")
        if len(attached) > 1 and boundaries:
            raise ValueError("Internal HVAC junction cannot be AMBIENT or VENT")
        if len(attached) > 10:
            raise ValueError("FDS HVAC nodes support at most ten ducts")
        xyz, junction_loss = ports[keys[0]].world_position, []
        if here:
            xyz, junction_loss = _junction(here[0], junctions[here[0]], ports, owners, specs, duct_ids, attached, model)
        node = HvacNode(id=node_id, port_keys=keys, entity_keys=sorted({owners[k] for k in keys}),
                        xyz=xyz, duct_ids=attached, boundary=boundaries[0] if boundaries else None,
                        junction_loss=junction_loss)
        if node.boundary and node.boundary.kind == "VENT":
            xb = node.boundary.vent_xb
            domain = model.simulation_domain
            if domain is None or any(xb[i] < domain.to_xb()[i] - 1e-8 if i % 2 == 0 else xb[i] > domain.to_xb()[i] + 1e-8 for i in range(6)):
                raise ValueError("HVAC CFD vent must lie within the declared simulation domain")
            if any(node.xyz[i] < xb[2*i] - 0.001 or node.xyz[i] > xb[2*i+1] + 0.001 for i in range(3)):
                raise ValueError("HVAC source endpoint must lie on its CFD vent")
            axis = next(i for i in range(3) if xb[2*i] == xb[2*i+1])
            def on_face(bounds):
                box = bounds.to_xb()
                return (any(abs(xb[2*axis] - box[j]) < 1e-8 for j in (2*axis, 2*axis+1))
                        and all(box[2*i] <= xb[2*i] + 1e-8 and box[2*i+1] >= xb[2*i+1] - 1e-8 for i in range(3) if i != axis))
            if not on_face(domain) and not any(e.mapping_strategy == MappingStrategy.OBST and e.bounding_box and on_face(e.representation_bounds or e.bounding_box) for e in model.elements):
                raise ValueError("HVAC vent must lie on a supported OBST or mesh boundary face; GEOM vent coupling is not yet supported")
        nodes.append(node)
        for key in keys:
            port_node[key] = node_id
    ducts = []
    for e in (e for e in selected if e.entity_key in specs):
        spec = specs[e.entity_key]
        distance = math.dist(*(p.world_position for p in e.ports))
        length = spec.length_m if spec.length_m is not None else distance
        if length <= 0 or length + 0.001 < distance:
            raise ValueError("HVAC length must be positive and cannot be shorter than the port chord")
        ordered_ports = e.ports
        if len(e.ports) == 2:
            def port_flow_order(p):
                direction = (getattr(p, "flow_direction", None) or "").upper()
                return 0 if direction == "SINK" else 1 if direction == "SOURCE" else 0.5
            ordered_ports = sorted(e.ports, key=port_flow_order)
        ducts.append(HvacDuct(id=duct_ids[e.entity_key], entity_key=e.entity_key,
                              node_ids=tuple(port_node[p.port_key] for p in ordered_ports), length_m=length, spec=spec))
    return HvacNetworkPlan(nodes=sorted(nodes, key=lambda n: n.id), ducts=sorted(ducts, key=lambda d: d.id))


def _junction(entity_key, spec, ports, owners, specs, duct_ids, attached, model):
    """Node position and FDS LOSS(i,j) entries of one junction, from reviewed per-port-pair losses."""
    own = [k for k in ports if owners[k] == entity_key]
    neighbour = {}
    for port in own:
        ducts = {
            duct_ids[owners[b]]
            for edge in model.mep_graph.connections
            for a, b in ((edge.source_port_id, edge.target_port_id), (edge.target_port_id, edge.source_port_id))
            if a == port and b in ports and owners[b] in specs
        }
        if len(ducts) != 1:
            raise ValueError(f"HVAC junction port must connect to exactly one duct: {entity_key}")
        neighbour[port] = next(iter(ducts))
    if sorted(neighbour.values()) != attached:
        raise ValueError(f"Each HVAC junction port needs its own duct: {entity_key}")
    given = {(x.from_port, x.to_port): x.k for x in spec.losses}
    expected = {(a, b) for a in own for b in own if a != b}
    if set(given) != expected:
        raise ValueError(
            f"HVAC junction needs one reviewed loss for every ordered port pair: {entity_key}; "
            f"missing {len(expected - set(given))}, unknown {len(set(given) - expected)}"
        )
    position = {duct: index + 1 for index, duct in enumerate(attached)}
    loss = sorted((position[neighbour[a]], position[neighbour[b]], k) for (a, b), k in given.items())
    centre = tuple(sum(ports[k].world_position[axis] for k in own) / len(own) for axis in range(3))
    return centre, loss
