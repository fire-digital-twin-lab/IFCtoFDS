"""Compare two FDS decks by the space their obstructions fill, without IFC provenance.

    python scripts/compare-fds-decks.py ours.fds other.fds [--json out.json] [--top 10]

Use it to compare an IFCtoFDS deck with a deck built in PyroSim from the same IFC, or a deck before and after it
was opened and saved in PyroSim. For each deck it reads OBST, GEOM and HOLE records (FDS cuts HOLEs out of OBSTs
only), unions them and reports: solid volume, intersection, IoU, the volume only one deck fills and where it lies,
the meshes, the `! IFC_SOURCE` provenance lines still present, and the HVAC records with their node LOSS(i,j)
entries. It measures and lists; it never decides whether a difference is acceptable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ifc_to_fds.geometry.boolean import solid_boolean  # noqa: E402
from ifc_to_fds.geometry.mesh import as_trimesh, valid_solid  # noqa: E402
from ifc_to_fds.validation.parser import parse_fds  # noqa: E402

# Measured at their initial state only (MULT_ID copies, CTRL/DEVC removal are not modelled); they are listed in `flagged`.
UNMODELLED = ("MULT_ID", "CTRL_ID", "DEVC_ID")


def _solid(record):
    mesh = record.mesh()
    return as_trimesh(mesh) if valid_solid(mesh) else None


def deck_space(text):
    """(trimesh of the filled space or None, summary dict) for one deck."""
    parsed = parse_fds(text, require_core_namelists=False)
    kinds = Counter(r.kind for r in parsed.records)
    skipped, flagged = Counter(), Counter()
    obst, holes, geoms = [], [], []
    for record in parsed.records:
        if record.kind not in ("OBST", "HOLE", "GEOM"):
            continue
        if any(key in record.values for key in UNMODELLED):
            flagged[f"{record.kind} with {'/'.join(k for k in UNMODELLED if k in record.values)}"] += 1
        solid = _solid(record)
        if solid is None:
            skipped[f"{record.kind} without volume (thin or invalid)"] += 1
            continue
        {"OBST": obst, "HOLE": holes, "GEOM": geoms}[record.kind].append(solid)
    space = solid_boolean(obst, "union") if len(obst) > 1 else (obst[0] if obst else None)
    if space is not None and holes:
        space = solid_boolean([space, *holes], "difference")
    pieces = [m for m in (space, *geoms) if m is not None and len(m.faces)]
    space = solid_boolean(pieces, "union") if len(pieces) > 1 else (pieces[0] if pieces else None)
    meshes = [r for r in parsed.records if r.kind == "MESH"]
    hvac = [r for r in parsed.records if r.kind == "HVAC"]
    summary = dict(
        records={k: kinds[k] for k in sorted(kinds)},
        skipped=dict(skipped),
        flagged=dict(flagged),
        # Records the strict parser refused (e.g. zero-thickness OBST) are not measured; their first lines are listed.
        parse_errors=len(parsed.errors),
        parse_error_samples=[e.splitlines()[0][:160] + (" | " + e.splitlines()[1].strip()[:120] if len(e.splitlines()) > 1 else "") for e in parsed.errors[:10]],
        unsupported_fields=len(parsed.unsupported),
        solid_volume_m3=float(space.volume) if space is not None else 0.0,
        meshes=len(meshes),
        cells=int(sum(np.prod(r.values["IJK"]) for r in meshes if len(r.values.get("IJK", [])) == 3)),
        provenance_lines=sum(1 for line in text.splitlines() if line.lstrip().startswith("! IFC_SOURCE")),
        hvac=dict(Counter(str(r.values.get("TYPE_ID", ["?"])[0]) for r in hvac)),
        node_loss_pairs=sum(1 for r in hvac for key in r.values if re.fullmatch(r"LOSS\(\d+,\d+\)", key)),
    )
    return space, summary


def _regions(mesh, top):
    if mesh is None or not len(mesh.faces):
        return []
    parts = sorted(mesh.split(only_watertight=False), key=lambda p: -abs(p.volume))[:top]
    return [dict(volume_m3=round(abs(float(p.volume)), 9), bounds=np.round(p.bounds.ravel(), 4).tolist()) for p in parts]


def compare(text_a, text_b, top=10):
    a, deck_a = deck_space(text_a)
    b, deck_b = deck_space(text_b)
    result = dict(a=deck_a, b=deck_b)
    if a is None or b is None:
        result["comparison"] = dict(note="one deck fills no volume")
        return result
    if np.array_equal(a.vertices, b.vertices) and np.array_equal(a.faces, b.faces):
        result["comparison"] = dict(method="IDENTICAL_SPACE", iou=1.0, intersection_m3=float(a.volume),
                                    only_a_m3=0.0, only_b_m3=0.0, only_a_regions=[], only_b_regions=[])
        return result
    # Intersection is derived from the two differences: on a real deck (B) Manifold's direct intersection lost
    # ~0.3% on coincident faces, while each difference stayed within ~2e-4 m3. Small only_* volumes are that noise.
    only_a = solid_boolean([a, b], "difference")
    only_b = solid_boolean([b, a], "difference")
    va, vb = abs(float(only_a.volume)), abs(float(only_b.volume))
    vi = float(a.volume) - va
    union = float(a.volume) + vb
    result["comparison"] = dict(
        method="BOOLEAN_DIFFERENCES", iou=vi / union if union > 0 else 0.0, intersection_m3=vi,
        only_a_m3=va, only_b_m3=vb,
        only_a_regions=_regions(only_a, top), only_b_regions=_regions(only_b, top),
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck_a", type=Path)
    parser.add_argument("deck_b", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--top", type=int, default=10, help="largest regions filled by only one deck")
    args = parser.parse_args(argv)
    result = compare(*(p.read_text(encoding="utf-8", errors="replace") for p in (args.deck_a, args.deck_b)), args.top)
    text = json.dumps(result, indent=2)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
