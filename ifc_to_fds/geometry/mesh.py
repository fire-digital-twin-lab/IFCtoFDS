"""Geometric mesh utilities, manifold checks, and bounding box calculation.
"""

from typing import Dict, List, Optional, Set, Tuple
import math

from ifc_to_fds.core.canonical import BoundingBox, TriangleMesh


def bounds_for_vertices(vertices: List[List[float]]) -> Optional[BoundingBox]:
    if not vertices:
        return None
    xmin = min(v[0] for v in vertices)
    xmax = max(v[0] for v in vertices)
    ymin = min(v[1] for v in vertices)
    ymax = max(v[1] for v in vertices)
    zmin = min(v[2] for v in vertices)
    zmax = max(v[2] for v in vertices)
    return BoundingBox(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, zmin=zmin, zmax=zmax)


def inspect_mesh_quality(mesh: TriangleMesh) -> Dict[str, int]:
    """Audits triangle mesh for degenerate faces, open edges, and non-manifold edges."""
    verts = mesh.vertices
    faces = mesh.faces

    degenerate_faces = 0
    edge_counts: Dict[Tuple[int, int], int] = {}
    directed_edges: Set[Tuple[int, int]] = set()
    inconsistent_edges = 0

    for f in faces:
        if len(f) < 3:
            degenerate_faces += 1
            continue
        v0, v1, v2 = f[0], f[1], f[2]
        if v0 == v1 or v1 == v2 or v2 == v0:
            degenerate_faces += 1
            continue

        p0, p1, p2 = verts[v0], verts[v1], verts[v2]
        # Cross product to check area
        ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
        bx, by, bz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
        cx = ay * bz - az * by
        cy = az * bx - ax * bz
        cz = ax * by - ay * bx
        area = 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
        if area < 1e-8:
            degenerate_faces += 1

        # Directed and undirected edges
        edges = [(v0, v1), (v1, v2), (v2, v0)]
        for ea, eb in edges:
            undirected = (min(ea, eb), max(ea, eb))
            edge_counts[undirected] = edge_counts.get(undirected, 0) + 1
            if (ea, eb) in directed_edges:
                inconsistent_edges += 1
            directed_edges.add((ea, eb))

    open_edges = sum(1 for count in edge_counts.values() if count == 1)
    non_manifold_edges = sum(1 for count in edge_counts.values() if count > 2)

    return {
        "degenerate_faces": degenerate_faces,
        "open_edges": open_edges,
        "non_manifold_edges": non_manifold_edges,
        "inconsistent_edges": inconsistent_edges,
        "is_closed_manifold": 1 if (open_edges == 0 and non_manifold_edges == 0 and len(faces) > 0) else 0,
    }
