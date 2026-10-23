"""Prove the GEOM surfaces actually emitted by FDS, separately from cut cells."""

import hashlib
from collections import Counter

import numpy as np

from ifc_to_fds.domain.validation import GateResult, GateStatus
from ifc_to_fds.modules.fds.api import parse_fds
from ifc_to_fds.modules.geometry.api import compare_solids, metrics_pass


def verify_solver_surfaces(fds_text, binaries, config, binary_reader):
    evidence = {
        "scope": "SOLVER_STATIC_GEOM_SURFACES_ONLY",
        "cut_cell_occupancy": "NOT_VERIFIED",
        "files": {},
    }

    def result(status, reason):
        return GateResult(
            status=status, reason=reason, required=False, evidence=evidence
        )

    parsed = parse_fds(fds_text)
    if parsed.errors or parsed.unsupported:
        return result(
            GateStatus.INCONCLUSIVE,
            "Solver surface audit requires supported static FDS syntax",
        )
    records = [r for r in parsed.records if r.kind == "GEOM"]
    if not records:
        return result(GateStatus.NOT_APPLICABLE, "No GEOM surface in input")
    heads = [r for r in parsed.records if r.kind == "HEAD"]
    if len(heads) != 1:
        return result(GateStatus.INCONCLUSIVE, "Unambiguous CHID required")
    chid = heads[0].values["CHID"][0]
    expected = {f"{chid}_{r.id}.bingeom": r for r in records}
    if set(expected) != set(binaries):
        return result(
            GateStatus.FAIL,
            "Solver BINGEOM surface inventory differs from serialized GEOM",
        )
    for filename, record in expected.items():
        data = binaries[filename]
        evidence["files"][filename] = {
            "sha256": hashlib.sha256(data).hexdigest(),
            "primitive_id": record.id,
        }
        try:
            mesh, surfaces = binary_reader(data)
            requested_surfaces = record.values["FACES"][3::4]
            reference = record.mesh()
            measured = compare_solids(reference, [mesh])
            evidence["files"][filename]["comparison"] = measured
            if not metrics_pass(measured, config):
                return result(
                    GateStatus.FAIL, f"Solver GEOM surface changed: {record.id}"
                )
            if not measured["surface_proven"]:
                return result(
                    GateStatus.INCONCLUSIVE,
                    f"Solver GEOM full surface not proved: {record.id}",
                )
            if len(surfaces) != len(mesh.faces):
                raise ValueError("Solver face/surface counts differ")
            # Bind each surface to its oriented geometric triangle. Comparing
            # an index list separately from the whole solid admits reassignment
            # when two triangles exchange positions in the face table.
            def triangles(solid, assignments, with_surfaces=True):
                counts = Counter()
                for face, surface in zip(solid.faces, assignments):
                    points = tuple(tuple(solid.vertices[i]) for i in face)
                    oriented = min(points[n:] + points[:n] for n in range(3))
                    counts[(surface, oriented) if with_surfaces else oriented] += 1
                return counts

            bound_equal = triangles(reference, requested_surfaces) == triangles(
                mesh, surfaces
            )
            same_indices = np.array_equal(reference.faces, mesh.faces)
            same_vertex_shape = np.shape(reference.vertices) == np.shape(mesh.vertices)
            if bound_equal:
                proof = "ORIENTED_TRIANGLE_SURFACE_MULTISET"
            elif same_indices and same_vertex_shape and surfaces == requested_surfaces:
                # Full-solid comparison above bounds the displacement of these
                # corresponding vertices using the approved audit tolerance.
                proof = "CORRESPONDING_TRIANGLES_WITH_APPROVED_TOLERANCE"
            elif len(set(requested_surfaces + surfaces)) == 1:
                proof = "SINGLE_SURFACE_FULL_SOLID"
            elif triangles(reference, requested_surfaces, False) == triangles(
                mesh, surfaces, False
            ):
                return result(
                    GateStatus.FAIL,
                    f"Solver per-face surface assignments differ: {record.id}",
                )
            else:
                return result(
                    GateStatus.INCONCLUSIVE,
                    f"Solver triangle-surface correspondence not proved: {record.id}",
                )
            evidence["files"][filename]["surface_assignment_proof"] = proof
        except ValueError as exc:
            return result(GateStatus.FAIL, f"Invalid solver BINGEOM {record.id}: {exc}")
        except RuntimeError as exc:
            return result(GateStatus.INCONCLUSIVE, str(exc))
    return result(
        GateStatus.PASS,
        "All serialized GEOM solids and face surfaces preserved in solver BINGEOM; cut-cell occupancy is separate",
    )
