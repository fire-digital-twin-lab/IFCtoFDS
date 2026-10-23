"""Authored IFC4 test model with actual swept solids, not a surveyed building.

Ports and systems are explicitly written into the fixture. Production readers
must preserve them; they must never infer these connections for user models.
All devices are passive geometry; no airflow or suppression physics is claimed.
"""

from pathlib import Path

import numpy as np
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.system
import ifcopenshell.api.unit


def create_mep_geometry_ifc(path):
    f = ifcopenshell.api.project.create_file(version="IFC4")

    def root(kind, name, **kw):
        return ifcopenshell.api.root.create_entity(f, ifc_class=kind, name=name, **kw)

    project = root("IfcProject", "Authored MEP geometry acceptance fixture")
    ifcopenshell.api.unit.assign_unit(
        f, units=[ifcopenshell.api.unit.add_si_unit(f, unit_type="LENGTHUNIT")]
    )
    context = ifcopenshell.api.context.add_context(f, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        f,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )
    storey = root("IfcBuildingStorey", "MEP test level")
    storey.Elevation = 0.0
    ifcopenshell.api.aggregate.assign_object(
        f, products=[storey], relating_object=project
    )
    expected = {
        "fixture_kind": "AUTHORED_SYNTHETIC_GEOMETRY",
        "members": {},
        "connections": [],
    }
    specs = [
        (
            "VENTILATION",
            0.0,
            [
                ("IfcDuctSegment", "Duct", "RIGIDSEGMENT", 2.0),
                ("IfcDuctFitting", "Duct connector", "CONNECTOR", 0.5),
                ("IfcFan", "Fan housing", "NOTDEFINED", 0.4),
                ("IfcAirTerminal", "Terminal frame", "DIFFUSER", 0.1),
            ],
        ),
        (
            "FIREPROTECTION",
            2.0,
            [
                ("IfcPipeSegment", "Fire pipe", "RIGIDSEGMENT", 2.0),
                ("IfcPipeFitting", "Pipe connector", "CONNECTOR", 0.5),
                ("IfcValve", "Isolation valve body", "ISOLATING", 0.3),
                ("IfcFireSuppressionTerminal", "Sprinkler stem", "SPRINKLER", 0.15),
            ],
        ),
    ]
    for category, y, members in specs:
        system = root("IfcDistributionSystem", category, predefined_type=category)
        previous = None
        x = 0.0
        for index, (kind, name, predefined, length) in enumerate(members):
            product = root(kind, name, predefined_type=predefined)
            ifcopenshell.api.spatial.assign_container(
                f, products=[product], relating_structure=storey
            )
            ifcopenshell.api.system.assign_system(f, products=[product], system=system)
            if category == "VENTILATION":
                profile = f.create_entity(
                    "IfcRectangleHollowProfileDef",
                    ProfileType="AREA",
                    XDim=0.6,
                    YDim=0.4,
                    WallThickness=0.02,
                )
                area = 0.6 * 0.4 - 0.56 * 0.36
            elif kind == "IfcFireSuppressionTerminal":
                profile = f.create_entity(
                    "IfcCircleProfileDef", ProfileType="AREA", Radius=0.025
                )
                area = None
            else:
                profile = f.create_entity(
                    "IfcCircleHollowProfileDef",
                    ProfileType="AREA",
                    Radius=0.05,
                    WallThickness=0.005,
                )
                area = None
            rep = ifcopenshell.api.geometry.add_profile_representation(
                f, context=body, profile=profile, depth=length
            )
            ifcopenshell.api.geometry.assign_representation(
                f, product=product, representation=rep
            )
            matrix = np.eye(4)
            matrix[:3, :3] = [[0, 0, 1], [1, 0, 0], [0, 1, 0]]
            matrix[:3, 3] = [x, y, 1.0]
            ifcopenshell.api.geometry.edit_object_placement(
                f, product=product, matrix=matrix
            )
            ports = []
            for side in range(1 if index == len(members) - 1 else 2):
                port = ifcopenshell.api.system.add_port(f, element=product)
                port.Name = f"{name} {'inlet' if side == 0 else 'outlet'}"
                port.FlowDirection = "SINK" if side == 0 else "SOURCE"
                placement = matrix.copy()
                placement[:3, 3] = [x + side * length, y, 1.0]
                ifcopenshell.api.geometry.edit_object_placement(
                    f, product=port, matrix=placement
                )
                ports.append(port)
            if previous is not None:
                ifcopenshell.api.system.connect_port(
                    f, port1=previous, port2=ports[0], direction="SOURCE"
                )
                expected["connections"].append([previous.GlobalId, ports[0].GlobalId])
            previous = ports[-1]
            expected["members"][product.GlobalId] = {
                "ifc_type": kind,
                "system_global_id": system.GlobalId,
                "category": (
                    "FIRE_SUPPRESSION" if category == "FIREPROTECTION" else category
                ),
                "ports": [p.GlobalId for p in ports],
                "length_m": length,
                "analytic_volume_m3": area * length if area is not None else None,
                "axis_start": [x, y, 1.0],
                "axis_end": [x + length, y, 1.0],
            }
            x += length
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(path))
    return expected
