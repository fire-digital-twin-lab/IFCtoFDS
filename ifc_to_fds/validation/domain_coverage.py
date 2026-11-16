"""Do the serialized MESH boxes cover the declared simulation domain exactly?"""

from __future__ import annotations

from math import prod
from typing import Optional, Sequence

OVERLAP_TOLERANCE_M = 1e-4  # same scale as the domain-extent check; rounding of shared faces is not an overlap
GAP_RELATIVE_TOLERANCE = 1e-6


def _volume(xb: Sequence[float]) -> float:
    return prod(xb[2 * k + 1] - xb[2 * k] for k in range(3))


def mesh_coverage_problem(meshes: Sequence[Sequence[float]], domain: Sequence[float]) -> Optional[str]:
    """Return why the MESH boxes do not tile `domain`, or None when they do.

    For axis-aligned boxes whose union already spans the domain extents, three facts decide it: no two
    boxes overlap, and their volumes add up to the domain volume. Overlap is checked first so that an
    overlap cannot hide a gap of the same volume.
    """
    for i, first in enumerate(meshes):
        for j in range(i + 1, len(meshes)):
            second = meshes[j]
            if all(
                min(first[2 * k + 1], second[2 * k + 1]) - max(first[2 * k], second[2 * k]) > OVERLAP_TOLERANCE_M
                for k in range(3)
            ):
                return f"MESH {i + 1} and MESH {j + 1} overlap"
    total = _volume(domain)
    gap = total - sum(_volume(m) for m in meshes)
    if total > 0 and gap > GAP_RELATIVE_TOLERANCE * total:
        return (
            f"MESH records leave {gap:.4g} m3 ({100.0 * gap / total:.1f}%) of the declared simulation "
            "domain without a computational mesh"
        )
    return None
