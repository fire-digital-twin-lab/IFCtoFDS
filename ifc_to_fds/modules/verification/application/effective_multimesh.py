"""Effective OBST evidence for adjacent, uniform meshes tiling one axis."""

from fractions import Fraction
import hashlib
import re

from ifc_to_fds.domain.validation import GateResult, GateStatus


def effective_multimesh(parsed, smv_text, single_mesh_checker):
    meshes = [r for r in parsed.records if r.kind == "MESH"]
    evidence = {
        "smv_sha256": hashlib.sha256(smv_text.encode()).hexdigest(),
        "meshes": [],
    }

    def unknown(reason):
        return GateResult(
            status=GateStatus.INCONCLUSIVE, reason=reason, evidence=evidence
        )

    # Establish an unambiguous rectangular union before clipping obstacles into
    # per-mesh pieces. Overlapping, gapped and arbitrary AMR layouts are excluded.
    tiled = False
    for axis in range(3):
        ordered = sorted(meshes, key=lambda r: r.values["XB"][2 * axis])
        others = [k for k in range(3) if k != axis]
        if all(
            all(
                m.values["XB"][2 * k : 2 * k + 2]
                == ordered[0].values["XB"][2 * k : 2 * k + 2]
                for k in others
            )
            for m in ordered
        ) and all(
            a.values["XB"][2 * axis + 1] == b.values["XB"][2 * axis]
            for a, b in zip(ordered, ordered[1:])
        ):
            tiled = True
            break
    if not tiled:
        return unknown(
            "Effective multi-mesh audit requires adjacent meshes tiling one axis"
        )
    cell_sizes = [
        tuple(
            (Fraction(m.values["XB"][2 * k + 1]) - Fraction(m.values["XB"][2 * k]))
            / int(m.values["IJK"][k])
            for k in range(3)
        )
        for m in meshes
    ]
    if any(s != cell_sizes[0] for s in cell_sizes):
        return unknown(
            "Different mesh cell sizes require additional interface evidence"
        )
    blocks = re.split(r"(?m)^GRID\s+", smv_text)[1:]
    if len(blocks) != len(meshes):
        return unknown("SMV mesh inventory differs or GRID sections are missing")
    bounds = [
        (
            min(m.values["XB"][i] for m in meshes)
            if i % 2 == 0
            else max(m.values["XB"][i] for m in meshes)
        )
        for i in range(6)
    ]
    expected = {r.id: r.values["XB"] for r in parsed.primitives if r.kind == "OBST"}
    if any(
        any(b[i] < bounds[i] if i % 2 == 0 else b[i] > bounds[i] for i in range(6))
        for b in expected.values()
    ):
        return unknown("Out-of-domain obstacles require an explicit boundary audit")
    merged = {}
    for mesh, block in zip(meshes, blocks):
        label = block.splitlines()[0].strip()
        if mesh.id and label != mesh.id:
            return unknown("SMV mesh identity/order differs from input")
        domain = mesh.values["XB"]
        subset = "&HEAD CHID='effective_subset' /\n&TIME T_END=0 /\n"
        subset += (
            "&MESH IJK="
            + ",".join(str(int(x)) for x in mesh.values["IJK"])
            + ", XB="
            + ",".join(map(str, domain))
            + " /\n"
        )
        for pid, original in expected.items():
            clipped = [
                (
                    max(original[i], domain[i])
                    if i % 2 == 0
                    else min(original[i], domain[i])
                )
                for i in range(6)
            ]
            if any(clipped[i + 1] <= clipped[i] for i in (0, 2, 4)):
                continue
            subset += (
                "&OBST ID='"
                + pid.replace("'", "''")
                + "', XB="
                + ",".join(map(str, clipped))
                + " /\n"
            )
        gate = single_mesh_checker(subset + "&TAIL /\n", "GRID " + block)
        evidence["meshes"].append({"id": label, **gate.model_dump(mode="json")})
        if gate.status != GateStatus.PASS:
            return GateResult(
                status=gate.status,
                reason=f"Mesh {label}: {gate.reason}",
                evidence=evidence,
            )
        for pid, piece in gate.evidence["effective_bounds"].items():
            if pid not in merged:
                merged[pid] = piece[:]
            else:
                merged[pid] = [
                    (
                        min(merged[pid][i], piece[i])
                        if i % 2 == 0
                        else max(merged[pid][i], piece[i])
                    )
                    for i in range(6)
                ]
    evidence["effective_bounds"] = merged
    if set(merged) != set(expected):
        return GateResult(
            status=GateStatus.FAIL,
            reason="Solver obstacle inventory differs across meshes",
            evidence=evidence,
        )
    # A gap straddling a mesh interface may close even if each individual mesh
    # passes. Check global pairwise clearances after joining per-ID fragments.
    ids = list(expected)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            a, b, aa, bb = expected[left], expected[right], merged[left], merged[right]
            for axis in range(3):
                if not all(
                    min(a[2 * k + 1], b[2 * k + 1]) > max(a[2 * k], b[2 * k])
                    for k in range(3)
                    if k != axis
                ):
                    continue
                gap = max(b[2 * axis] - a[2 * axis + 1], a[2 * axis] - b[2 * axis + 1])
                effective_gap = max(
                    bb[2 * axis] - aa[2 * axis + 1], aa[2 * axis] - bb[2 * axis + 1]
                )
                if gap > 1e-8 and effective_gap <= 1e-8:
                    return GateResult(
                        status=GateStatus.FAIL,
                        reason=f"Passage closed across mesh interface: {left}, {right}",
                        evidence=evidence,
                    )
    return GateResult(
        status=GateStatus.PASS,
        reason="Adjacent uniform meshes: per-mesh OBST indices and cross-interface clearances verified",
        evidence=evidence,
    )
