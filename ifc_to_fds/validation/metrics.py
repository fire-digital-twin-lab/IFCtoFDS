"""Validation and Geometric Verification Metrics.

Calculates volumetric Intersection over Union (IoU), surface deviations,
and opening retention rates between IFC source and FDS models.
"""

from typing import Optional
from ifc_to_fds.core.canonical import BoundingBox, CanonicalElement


def calculate_bbox_iou(b1: Optional[BoundingBox], b2: Optional[BoundingBox]) -> float:
    """Calculates Intersection over Union (IoU) of two 3D bounding boxes."""
    if not b1 or not b2:
        return 0.0

    # Intersection bounds
    ixmin = max(b1.xmin, b2.xmin)
    ixmax = min(b1.xmax, b2.xmax)
    iymin = max(b1.ymin, b2.ymin)
    iymax = min(b1.ymax, b2.ymax)
    izmin = max(b1.zmin, b2.zmin)
    izmax = min(b1.zmax, b2.zmax)

    if ixmax <= ixmin or iymax <= iymin or izmax <= izmin:
        return 0.0

    intersection_vol = (ixmax - ixmin) * (iymax - iymin) * (izmax - izmin)
    v1 = b1.volume
    v2 = b2.volume
    union_vol = v1 + v2 - intersection_vol

    if union_vol <= 0:
        return 0.0
    return intersection_vol / union_vol


def verify_opening_retention(elem: CanonicalElement) -> bool:
    """Verifies that an element with openings has not been reverted to an uncarved solid."""
    if not elem.openings:
        return True

    if not elem.mesh or not elem.mesh.faces:
        return False

    # A simple extruded box has 12 triangle faces (2 per side).
    # Any wall with window or door boolean cutouts requires significantly more faces.
    if len(elem.mesh.faces) <= 12:
        return False

    return True
