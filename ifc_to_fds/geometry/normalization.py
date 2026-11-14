"""Bounded numerical normalization of freshly extracted source triangles.

This is not a hole-filling or shape-repair backend.  Every output triangle has
one input triangle, with the same vertices up to a recorded roundoff budget and
an optional change of winding.  A refused candidate leaves the raw mesh intact.
Independent readers must call this on their own freshly extracted IFC mesh.
"""

from collections import defaultdict
import hashlib
import json
from typing import Any, Dict, Optional, Tuple

import numpy as np
from scipy.spatial import cKDTree

from ifc_to_fds.domain.bim import GeometryStatus
from .mesh import inspect_mesh_quality


NORMALIZATION_REVISION = "numerical-seams-8ulp-cap-1e-12-single-shell-winding-v1"
ADAPTIVE_NORMALIZATION_REVISION = "adaptive-cad-1e-6-cap-1e-5-single-shell-winding-v1"
MAX_DISPLACEMENT_M = 1e-12
MAX_ULPS = 8
CAD_TOLERANCE_M = 1e-6
MAX_CAD_DISPLACEMENT_M = 1e-5


def _compute_mesh_volume(vertices: np.ndarray, faces: np.ndarray) -> float:
    if len(faces) == 0 or len(vertices) == 0:
        return 0.0
    triangles = vertices[faces] - vertices.mean(axis=0)
    vol = float(
        np.einsum(
            "ij,ij->i", triangles[:, 0],
            np.cross(triangles[:, 1], triangles[:, 2]),
        ).sum() / 6.0
    )
    return abs(vol)


def _digest(mesh):
    # This includes only the source triangles, not mutable quality annotations.
    return hashlib.sha256(
        json.dumps(
            {"vertices": mesh.vertices, "faces": mesh.faces},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _solid(quality):
    return bool(
        quality["finite"]
        and quality["is_closed_manifold"]
        and quality["positive_volume"]
    )


def _weld(vertices, faces, tolerance):
    """Use existing vertices as representatives; never average or chain welds."""
    tree = cKDTree(vertices)
    representatives = []
    source_representatives = {}
    mapping = np.empty(len(vertices), dtype=np.int64)
    for index, point in enumerate(vertices):
        candidates = sorted(tree.query_ball_point(point, tolerance))
        representative = next(
            (other for other in candidates if other in source_representatives),
            None,
        )
        if representative is None:
            source_representatives[index] = len(representatives)
            mapping[index] = len(representatives)
            representatives.append(point)
        else:
            mapping[index] = source_representatives[representative]
    return np.asarray(representatives), mapping[faces], mapping


def _orient_single_shell(vertices, faces):
    edges = defaultdict(list)
    for index, face in enumerate(faces):
        for a, b in zip(face, np.roll(face, -1)):
            edges[tuple(sorted((int(a), int(b))))].append((index, bool(a < b)))
    if any(len(entries) != 2 for entries in edges.values()):
        return None, "OPEN_OR_NON_MANIFOLD_SHELL"
    adjacency = defaultdict(list)
    for (a, direction_a), (b, direction_b) in edges.values():
        opposite = direction_a == direction_b
        adjacency[a].append((b, opposite))
        adjacency[b].append((a, opposite))
    flips = {0: False}
    pending = [0]
    while pending:
        current = pending.pop()
        for other, opposite in adjacency[current]:
            desired = flips[current] ^ opposite
            if other in flips:
                if flips[other] != desired:
                    return None, "NON_ORIENTABLE_SHELL"
            else:
                flips[other] = desired
                pending.append(other)
    if len(flips) != len(faces):
        # A negative inner cavity shell can be intentional. Never choose the
        # orientation of multiple shells independently without containment proof.
        return None, "AMBIGUOUS_MULTI_SHELL_ORIENTATION"
    output = faces.copy()
    for index, flip in flips.items():
        if flip:
            output[index] = output[index, ::-1]
    # Translate before measuring signed volume to avoid world-origin cancellation.
    triangles = vertices[output] - vertices.mean(axis=0)
    volume = float(
        np.einsum(
            "ij,ij->i", triangles[:, 0],
            np.cross(triangles[:, 1], triangles[:, 2]),
        ).sum() / 6.0
    )
    if volume < 0:
        output = output[:, ::-1]
    return output, None


def normalize_source_mesh(
    mesh,
    adaptive_cad: bool = False,
    cad_tolerance: float = CAD_TOLERANCE_M,
    max_tolerance: float = MAX_CAD_DISPLACEMENT_M,
    min_volume_ratio: float = 0.999,
    max_displacement: Optional[float] = None,
):
    """Return ``(mesh, proof)`` without mutating the raw input.

    ``NORMALIZED`` proves only bounded triangle correspondence and the existing
    valid-solid predicates. It does not prove openings, self-intersection,
    enclosure, source fidelity, or solver behavior; those audits remain required.
    """
    if max_displacement is not None and max_displacement > MAX_DISPLACEMENT_M:
        adaptive_cad = True
        cad_tolerance = max_displacement
        max_tolerance = max(max_displacement, max_tolerance)

    active_revision = ADAPTIVE_NORMALIZATION_REVISION if adaptive_cad else NORMALIZATION_REVISION
    active_cap = max_tolerance if adaptive_cad else MAX_DISPLACEMENT_M

    quality = inspect_mesh_quality(mesh)
    digest = _digest(mesh)
    proof = dict(
        revision=active_revision,
        status="NOT_NEEDED",
        reason="Raw extracted triangles already satisfy solid predicates",
        source_mesh_sha256=digest,
        result_mesh_sha256=digest,
        raw_quality=quality,
        result_quality=quality,
        max_ulps=MAX_ULPS,
        arithmetic_cap_m=active_cap,
        tolerance_m=0.0,
        max_vertex_displacement_m=0.0,
        vertices_merged=0,
        vertex_map=[],
        faces_flipped=[],
        triangle_count_preserved=True,
        face_correspondence_preserved=True,
        geometry_repair_applied=False,
    )
    if _solid(quality):
        return mesh, proof

    def refuse(reason, candidate_quality=None):
        proof.update(status="REFUSED", reason=reason)
        if candidate_quality is not None:
            proof["candidate_quality"] = candidate_quality
        return mesh, proof

    if not quality["finite"]:
        return refuse("NON_FINITE_SOURCE_COORDINATES")
    if quality["invalid_indices"] or quality["degenerate_faces"]:
        return refuse("INVALID_OR_DEGENERATE_SOURCE_TRIANGLES")
    if not mesh.faces:
        return refuse("NO_SOURCE_TRIANGLES")
    if quality["non_manifold_edges"]:
        return refuse("NON_MANIFOLD_SOURCE_EDGES")
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    scale = max(1.0, float(np.abs(vertices).max()))
    if adaptive_cad:
        tolerance = min(max(float(np.spacing(scale)) * MAX_ULPS, cad_tolerance), max_tolerance)
    else:
        tolerance = min(float(np.spacing(scale)) * MAX_ULPS, MAX_DISPLACEMENT_M)
    proof["tolerance_m"] = tolerance
    output_vertices, output_faces = vertices, faces
    mapping = np.arange(len(vertices), dtype=np.int64)
    if quality["open_edges"]:
        try:
            output_vertices, output_faces, mapping = _weld(vertices, faces, tolerance)
        except (ValueError, OverflowError) as exc:
            proof["numerical_diagnostic"] = str(exc)
            return refuse("NUMERICAL_WELD_UNAVAILABLE")
    candidate = mesh.model_copy(
        deep=True,
        update=dict(vertices=output_vertices.tolist(), faces=output_faces.tolist()),
    )
    candidate_quality = inspect_mesh_quality(candidate)
    if any(candidate_quality[k] for k in (
        "invalid_indices", "degenerate_faces", "non_manifold_edges",
    )):
        return refuse("WELD_WOULD_COLLAPSE_OR_INVALIDATE_TRIANGLES", candidate_quality)
    unordered = np.sort(output_faces, axis=1)
    if len(np.unique(unordered, axis=0)) != len(output_faces):
        return refuse("DUPLICATE_SOURCE_SURFACES", candidate_quality)
    if candidate_quality["open_edges"]:
        return refuse("SOURCE_SURFACE_REMAINS_OPEN", candidate_quality)
    if not _solid(candidate_quality):
        output_faces, reason = _orient_single_shell(output_vertices, output_faces)
        if reason:
            return refuse(reason, candidate_quality)
        candidate.faces = output_faces.tolist()
        candidate_quality = inspect_mesh_quality(candidate)
    if not _solid(candidate_quality):
        return refuse("CANDIDATE_NOT_A_VALID_SOLID", candidate_quality)

    if adaptive_cad:
        raw_vol = _compute_mesh_volume(vertices, faces)
        cand_vol = _compute_mesh_volume(output_vertices, output_faces)
        if raw_vol > 1e-9:
            vol_ratio = cand_vol / raw_vol
            proof["volume_ratio"] = vol_ratio
            if vol_ratio < min_volume_ratio or vol_ratio > (2.0 - min_volume_ratio):
                return refuse("VOLUME_PRESERVATION_VIOLATED", candidate_quality)

    displacement = float(
        np.linalg.norm(vertices - output_vertices[mapping], axis=1).max()
    )
    if not np.isfinite(displacement) or displacement > tolerance:
        return refuse("ARITHMETIC_DISPLACEMENT_BUDGET_EXCEEDED", candidate_quality)
    # Each face retains its three mapped vertices, possibly in reverse order.
    # The largest vertex displacement also bounds the displacement of every
    # point with equal barycentric coordinates on the corresponding triangles.
    if not np.array_equal(np.sort(mapping[faces], axis=1), np.sort(output_faces, axis=1)):
        return refuse("TRIANGLE_CORRESPONDENCE_NOT_PROVED", candidate_quality)
    candidate.normals = None
    candidate.area = candidate.volume = None
    candidate.is_closed_manifold = True
    candidate.has_consistent_normals = True
    proof.update(
        status="NORMALIZED",
        reason="Bounded numerical vertex/triangle correspondence proved; full audits still required",
        result_mesh_sha256=_digest(candidate),
        result_quality=candidate_quality,
        max_vertex_displacement_m=displacement,
        vertices_merged=len(vertices) - len(output_vertices),
        vertex_map=mapping.tolist(),
        faces_flipped=np.flatnonzero(np.any(output_faces != mapping[faces], axis=1)).tolist(),
    )
    return candidate, proof


def normalize_element_geometry(
    target: Any,
    cad_tolerance: float = CAD_TOLERANCE_M,
    max_tolerance: float = MAX_CAD_DISPLACEMENT_M,
    min_volume_ratio: float = 0.999,
) -> Tuple[Any, Dict[str, Any]]:
    """Adaptive CAD tolerance normalization for elements or meshes.

    Allows welding micro-gaps up to cad_tolerance (default 1e-6 m, capped at max_tolerance 1e-5 m)
    from OpenCASCADE/IfcOpenShell triangulations, while strictly verifying volume preservation
    (> 99.9%) and non-degeneracy.
    """
    if target is None:
        return None, {"status": "NOT_APPLICABLE", "reason": "Target is None"}

    is_element = hasattr(target, "mesh")
    mesh_obj = target.mesh if is_element else target

    if mesh_obj is None:
        return target, {"status": "NOT_APPLICABLE", "reason": "No mesh on target"}

    normalized_mesh, proof = normalize_source_mesh(
        mesh_obj,
        adaptive_cad=True,
        cad_tolerance=cad_tolerance,
        max_tolerance=max_tolerance,
        min_volume_ratio=min_volume_ratio,
    )

    if is_element:
        if proof["status"] in ("NORMALIZED", "NOT_NEEDED"):
            target.mesh = normalized_mesh
            if hasattr(target, "geometry_status"):
                target.geometry_status = GeometryStatus.VALID
        return target, proof

    return normalized_mesh, proof

