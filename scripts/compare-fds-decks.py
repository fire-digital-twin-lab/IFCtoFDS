"""Compare two FDS decks by the space their obstructions fill, without IFC provenance.

    python scripts/compare-fds-decks.py ours.fds other.fds [--json out.json] [--top 10] [--clip-to-mesh] [--inventory inventory.json]

Use it to compare an IFCtoFDS deck with a deck built in PyroSim from the same IFC, or a deck before and after it
was opened and saved in PyroSim. For each deck it reads OBST, GEOM and HOLE records (FDS cuts HOLEs out of OBSTs
only), unions them and reports: solid volume, intersection, IoU, the volume only one deck fills and where it lies,
the meshes, the `! IFC_SOURCE` provenance lines still present, and the HVAC records with their node LOSS(i,j)
entries. It measures and lists; it never decides whether a difference is acceptable.

A PyroSim deck needs three accommodations, all applied to an in-memory copy: the banner before the first namelist is
dropped, repeated IDs get a suffix, and zero-thickness OBSTs (valid in FDS, no volume) are counted by number and area
under `thin_obst` instead of being silently ignored. `--clip-to-mesh` clips both decks to the union of their MESH
records; `--inventory` (our inventory JSON) matches elements by the Revit id that ends both the IFC name and the PyroSim ID.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ifc_to_fds.geometry.boolean import solid_boolean  # noqa: E402
from ifc_to_fds.geometry.mesh import as_trimesh, valid_solid  # noqa: E402
from ifc_to_fds.validation.parser import parse_fds  # noqa: E402

# Measured at their initial state only (MULT_ID copies, CTRL/DEVC removal are not modelled); they are listed in `flagged`.
UNMODELLED = ("MULT_ID", "CTRL_ID", "DEVC_ID")


def _solid(record):
    mesh = record.mesh()
    return as_trimesh(mesh) if valid_solid(mesh) else None


def _clean_text(text):
    """Drop a banner before the first namelist and make repeated IDs unique (FDS accepts both, the strict parser not)."""
    start = text.find("&")
    text = text[start:] if start > 0 else text
    seen = Counter()

    def unique(match):
        seen[match.group(1)] += 1
        return match.group(0) if seen[match.group(1)] == 1 else f"ID='{match.group(1)}__dup{seen[match.group(1)]}'"

    return re.sub(r"(?<![A-Za-z_])ID='([^']*)'", unique, text)


def _numbers(text):
    return [float(x) for x in text.replace(" ", "").split(",") if x]


def _thin_obst(text):
    """(records, area m2) of OBSTs with zero thickness on one axis: no volume, still a barrier in FDS."""
    boxes = [_numbers(m) for m in re.findall(r"&OBST\b[^/]*?XB=([-+0-9.eE, ]+)", text)]
    sides = [sorted((b[1] - b[0], b[3] - b[2], b[5] - b[4])) for b in boxes if len(b) == 6]
    thin = [d for d in sides if d[0] < 1e-9]
    return len(thin), round(sum(d[1] * d[2] for d in thin), 3)


def deck_space(text):
    """(trimesh of the filled space or None, summary dict) for one deck."""
    parsed = parse_fds(_clean_text(text), require_core_namelists=False)
    thin_records, thin_area = _thin_obst(text)
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
        thin_obst=dict(records=thin_records, area_m2=thin_area),
        hvac=dict(Counter(str(r.values.get("TYPE_ID", ["?"])[0]) for r in hvac)),
        node_loss_pairs=sum(1 for r in hvac for key in r.values if re.fullmatch(r"LOSS\(\d+,\d+\)", key)),
    )
    return space, summary


def _regions(mesh, top):
    if mesh is None or not len(mesh.faces):
        return []
    parts = sorted(mesh.split(only_watertight=False), key=lambda p: -abs(p.volume))[:top]
    return [dict(volume_m3=round(abs(float(p.volume)), 9), bounds=np.round(p.bounds.ravel(), 4).tolist()) for p in parts]


def _mesh_domain(*texts):
    """Union bounding box of the MESH records of the given decks, or None."""
    boxes = [_numbers(m) for text in texts for m in re.findall(r"&MESH\b[^/]*?XB=([-+0-9.eE, ]+)", text)]
    boxes = [b for b in boxes if len(b) == 6]
    if not boxes:
        return None
    return [min(b[i] for b in boxes) for i in (0, 2, 4)], [max(b[i + 1] for b in boxes) for i in (0, 2, 4)]


def _clip(space, domain):
    if space is None or domain is None:
        return space
    lo, hi = domain
    box = trimesh.creation.box(extents=np.subtract(hi, lo))
    box.apply_translation(np.add(lo, hi) / 2)
    return solid_boolean([space, box], "intersection")


def compare(text_a, text_b, top=10, clip=False):
    a, deck_a = deck_space(text_a)
    b, deck_b = deck_space(text_b)
    result = dict(a=deck_a, b=deck_b)
    if clip:
        domain = _mesh_domain(text_a, text_b)
        result["clipped_to"] = None if domain is None else [np.round(domain[0], 4).tolist(), np.round(domain[1], 4).tolist()]
        a, b = _clip(a, domain), _clip(b, domain)
        for deck, space in ((deck_a, a), (deck_b, b)):
            deck["solid_volume_in_domain_m3"] = float(space.volume) if space is not None else 0.0
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


def _revit_id(name):
    return name.rsplit(":", 1)[-1].strip() if name and ":" in name else None


def compare_elements(text_a, text_b, inventory):
    """Match deck A (IFCtoFDS, `! IFC_SOURCE` entity keys) with deck B (PyroSim) by the id ending the IFC name / OBST ID."""
    meta = {e["entity_key"]: (e.get("name") or "", e.get("ifc_type")) for e in inventory["elements"]}
    ours, theirs = {}, {}
    for text, side in ((text_a, ours), (text_b, theirs)):
        for record in parse_fds(_clean_text(text), require_core_namelists=False).records:
            if record.kind not in ("OBST", "GEOM"):
                continue
            solid = _solid(record)
            if solid is None:
                continue
            if side is ours:
                source = getattr(record, "source", None) or {}
                key = source.get("entity_key") or (source.get("entity_keys") or [None])[0]
                name, typ = meta.get(key, ("", None))
                rid = _revit_id(name)
            else:
                name = re.sub(r"__dup\d+$", "", record.id or "")
                rid, typ = _revit_id(name), name.split(":")[0]
            if rid:
                side.setdefault(rid, [typ, []])[1].append(solid)
    union = lambda parts: solid_boolean(parts, "union") if len(parts) > 1 else parts[0]
    matched = []
    for rid in ours.keys() & theirs.keys():
        a, b = union(ours[rid][1]), union(theirs[rid][1])
        only_a = abs(float(solid_boolean([a, b], "difference").volume))
        only_b = abs(float(solid_boolean([b, a], "difference").volume))
        total = float(a.volume) + only_b
        matched.append((ours[rid][0], float(a.volume), float(b.volume), (float(a.volume) - only_a) / total if total > 0 else 0.0))
    by_type = {}
    for typ, va, vb, iou in matched:
        row = by_type.setdefault(typ, dict(n=0, a_m3=0.0, b_m3=0.0, ious=[]))
        row["n"] += 1
        row["a_m3"] += va
        row["b_m3"] += vb
        row["ious"].append(iou)
    quart = lambda values: np.round(np.percentile(values, [10, 25, 50, 75, 90]), 3).tolist() if values else None
    return dict(
        a_elements=len(ours), b_elements=len(theirs), matched=len(matched),
        only_a=len(ours.keys() - theirs.keys()), only_b=len(theirs.keys() - ours.keys()),
        iou_quartiles_p10_p25_p50_p75_p90=quart([m[3] for m in matched]),
        volume_ratio_b_over_a_quartiles=quart([m[2] / m[1] for m in matched if m[1] > 0]),
        by_type={t: dict(n=r["n"], a_m3=round(r["a_m3"], 3), b_m3=round(r["b_m3"], 3), median_iou=round(float(np.median(r["ious"])), 3))
                 for t, r in sorted(by_type.items(), key=lambda kv: -kv[1]["a_m3"])},
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deck_a", type=Path)
    parser.add_argument("deck_b", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--top", type=int, default=10, help="largest regions filled by only one deck")
    parser.add_argument("--clip-to-mesh", action="store_true", help="clip both decks to the union of their MESH records")
    parser.add_argument("--inventory", type=Path, help="IFCtoFDS inventory JSON: also match elements by Revit id")
    args = parser.parse_args(argv)
    texts = [p.read_text(encoding="utf-8", errors="replace") for p in (args.deck_a, args.deck_b)]
    result = compare(*texts, args.top, clip=args.clip_to_mesh)
    if args.inventory:
        result["elements"] = compare_elements(*texts, json.loads(args.inventory.read_text(encoding="utf-8")))
    text = json.dumps(result, indent=2)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
