"""The `&OBST` boxes FDS receives for an element, and whether a VENT rectangle lies on their solid/gas face.

One definition serves the exporter (what is written), the HVAC compiler (where a VENT may sit) and, through
the compiler, the independent HVAC check, so none of them can disagree about which boxes exist.
"""

from __future__ import annotations

from shapely.geometry import box as _rectangle
from shapely.ops import unary_union

from ifc_to_fds.domain.mapping.enums import MappingStrategy
from ifc_to_fds.geometry.mesh import is_axis_aligned_box
from ifc_to_fds.geometry.rectilinear import box_set_for

FACE_TOLERANCE_M = 1e-8
COVERAGE_RELATIVE_TOLERANCE = 1e-6


def emitted_obst_boxes(element):
    """[(xmin, xmax, ymin, ymax, zmin, zmax), ...]: one box, or the exact box cover of a rectilinear host."""
    if element.mapping_strategy != MappingStrategy.OBST or not element.bounding_box:
        return []
    if is_axis_aligned_box(element.mesh):
        return [(element.representation_bounds or element.bounding_box).to_xb()]
    return list(box_set_for(element.mesh) or [])


def vent_rests_on_solid_face(vent_xb, boxes) -> bool:
    """True when the whole VENT rectangle lies on a face with solid on exactly one side.

    A plane shared by two touching boxes is not a solid/gas interface: FDS has no exposed surface there to
    attach a VENT to (ERROR 818), so only the area covered by boxes on exactly one side of the plane counts.
    """
    axis = next(a for a in range(3) if vent_xb[2 * a] == vent_xb[2 * a + 1])
    plane = vent_xb[2 * axis]
    u, v = [a for a in range(3) if a != axis]

    def footprint(b):
        return _rectangle(b[2 * u], b[2 * v], b[2 * u + 1], b[2 * v + 1])

    below = [footprint(b) for b in boxes if abs(b[2 * axis + 1] - plane) < FACE_TOLERANCE_M]
    above = [footprint(b) for b in boxes if abs(b[2 * axis] - plane) < FACE_TOLERANCE_M]
    exposed = unary_union(below).symmetric_difference(unary_union(above))
    rectangle = _rectangle(vent_xb[2 * u], vent_xb[2 * v], vent_xb[2 * u + 1], vent_xb[2 * v + 1])
    return rectangle.difference(exposed).area <= COVERAGE_RELATIVE_TOLERANCE * rectangle.area
