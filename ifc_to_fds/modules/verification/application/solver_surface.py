"""Prove the GEOM surfaces actually emitted by FDS, separately from cut cells."""

import hashlib

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
            if surfaces != requested_surfaces:
                return result(
                    GateStatus.FAIL,
                    f"Solver per-face surface assignments differ: {record.id}",
                )
            measured = compare_solids(record.mesh(), [mesh])
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
        except ValueError as exc:
            return result(GateStatus.FAIL, f"Invalid solver BINGEOM {record.id}: {exc}")
        except RuntimeError as exc:
            return result(GateStatus.INCONCLUSIVE, str(exc))
    return result(
        GateStatus.PASS,
        "All serialized GEOM solids and face surfaces preserved in solver BINGEOM; cut-cell occupancy is separate",
    )
