"""Pilot for M2.4: FDS 6.11.1 cut-cell gas volume and open face area of real GEOM solids against exact booleans.

    python scripts/cutcell-pilot.py <deck.fds> <inventory.json> <out.json> [N]

Picks N GEOM records of a deck (stratified by IFC type and by whether the faces follow the grid axes), runs each in an
isolated deck on the deck's 0.2 m node lattice with probes placed on its surface, and writes the expected value (exact
boolean), the FDS value and the error of every probe. It only measures: the tolerance handed to the cut-cell module is
deliberately huge so every run reports its numbers, and no verdict is derived here. Needs the pinned FDS
(`IFCFDS_SOLVER`). Elements larger than MAX_CELLS cells are skipped, so large walls and slabs are not covered.
"""
import json
import math
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ifc_to_fds.geometry.boolean import solid_boolean
from ifc_to_fds.geometry.mesh import as_trimesh, valid_solid
from ifc_to_fds.validation import effective_cutcell
from ifc_to_fds.validation.acceptance import AuditConfig
from ifc_to_fds.validation.parser import parse_fds

DX = 0.2
MARGIN = 3
MAX_CELLS = 60000
deck_path, inv_path, out_path = sys.argv[1:4]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 24
rng = random.Random(0)

meta = {e["entity_key"]: e for e in json.load(open(inv_path, encoding="utf-8"))["elements"]}
parsed = parse_fds(open(deck_path, encoding="utf-8", errors="replace").read(), require_core_namelists=False)
candidates = []
for r in parsed.records:
    if r.kind != "GEOM":
        continue
    source = getattr(r, "source", None) or {}
    key = source.get("entity_key") or (source.get("entity_keys") or [None])[0]
    mesh = r.mesh()
    if not valid_solid(mesh):
        continue
    tm = as_trimesh(mesh)
    lo, hi = tm.bounds
    dims = hi - lo
    lo_d = np.floor((lo - MARGIN * DX) / DX) * DX
    hi_d = np.ceil((hi + MARGIN * DX) / DX) * DX
    cells = int(np.prod(np.round((hi_d - lo_d) / DX)))
    if cells > MAX_CELLS or cells < 64:
        continue
    n = tm.face_normals
    a = tm.area_faces
    aligned = float(a[(np.abs(n).max(axis=1) > math.cos(math.radians(2)))].sum() / a.sum())
    candidates.append(dict(key=key, type=(meta.get(key) or {}).get("ifc_type"), mesh=mesh, tm=tm, dims=dims.tolist(), cells=cells,
                           aligned_share=round(aligned, 3), lo_d=lo_d, hi_d=hi_d))
print("eligible by size:", len(candidates), "of GEOM", sum(1 for r in parsed.records if r.kind == "GEOM"))
for c in candidates:
    c["stratum"] = (c["type"], "aligned" if c["aligned_share"] > 0.95 else "tilted")
strata = {}
for c in candidates:
    strata.setdefault(c["stratum"], []).append(c)
print("strata:", {f"{k[0]}/{k[1]}": len(v) for k, v in sorted(strata.items(), key=lambda kv: str(kv[0]))})
picked = []
keys = sorted(strata, key=str)
i = 0
while len(picked) < min(N, len(candidates)):
    pool = strata[keys[i % len(keys)]]
    if pool:
        picked.append(pool.pop(rng.randrange(len(pool))))
    i += 1
    if i > 10000:
        break


def box_mesh(lo, hi):
    b = trimesh.creation.box(extents=np.subtract(hi, lo))
    b.apply_translation((np.add(lo, hi) / 2))
    return b


def snap(v, lo_d):
    return lo_d + np.round((v - lo_d) / DX) * DX


def probes_for(c):
    extras = {}
    tm, lo_d, hi_d = c["tm"], c["lo_d"], c["hi_d"]
    ijk = np.round((hi_d - lo_d) / DX).astype(int)
    solid_vol = float(tm.volume)
    probes = [dict(id="global_gas", bounds_m=tuple(np.round(np.ravel(np.column_stack([lo_d, hi_d])), 10)), expected=float(np.prod(hi_d - lo_d)) - solid_vol,
                   tolerance=1.0, units="m3")]
    pts, _ = trimesh.sample.sample_surface(tm, 200, seed=1)
    order = list(range(len(pts)))
    rng.shuffle(order)
    boxes = 0
    for idx in order:
        if boxes >= 6:
            break
        center = snap(pts[idx], lo_d)
        blo, bhi = center - 1.5 * DX, center + 1.5 * DX
        blo = np.round((blo - lo_d) / DX) * DX + lo_d
        bhi = blo + 3 * DX
        if np.any(blo <= lo_d + 1e-9) or np.any(bhi >= hi_d - 1e-9):
            continue
        inter = solid_boolean([tm, box_mesh(blo, bhi)], "intersection")
        gas = DX ** 3 * 27 - (abs(float(inter.volume)) if inter is not None and len(inter.faces) else 0.0)
        probes.append(dict(id=f"vol{boxes}", bounds_m=tuple(np.round(np.ravel(np.column_stack([blo, bhi])), 10)), expected=gas, tolerance=1.0, units="m3"))
        boxes += 1
    for axis in range(3):
        center = snap((tm.bounds[0] + tm.bounds[1]) / 2, lo_d)[axis]
        if not lo_d[axis] + DX < center < hi_d[axis] - DX:
            continue
        normal = np.zeros(3)
        normal[axis] = 1
        origin = np.zeros(3)
        origin[axis] = center
        from shapely.geometry import LineString, box as sbox
        from shapely.ops import polygonize, unary_union
        other = [a for a in range(3) if a != axis]
        segs = trimesh.intersections.mesh_plane(tm, normal, origin)
        if segs is None or not len(segs):
            continue
        lines = unary_union([LineString([(sg[0][other[0]], sg[0][other[1]]), (sg[1][other[0]], sg[1][other[1]])]) for sg in segs])
        polys = list(polygonize(lines))
        if not polys:
            continue
        sample, _ = trimesh.sample.sample_surface(tm, 400, seed=2)
        near = sample[np.abs(sample[:, axis] - center) < DX]
        if not len(near):
            continue
        p = snap(near[rng.randrange(len(near))], lo_d)
        rlo = np.round((p[other] - 1.5 * DX - lo_d[other]) / DX) * DX + lo_d[other]
        rhi = rlo + 3 * DX
        if np.any(rlo <= lo_d[other] + 1e-9) or np.any(rhi >= hi_d[other] - 1e-9):
            continue
        rect = sbox(rlo[0], rlo[1], rhi[0], rhi[1])
        region = None
        for poly in polys:
            region = poly if region is None else region.symmetric_difference(poly)  # even-odd: holes stay gas
        solid_area = region.intersection(rect).area
        bounds = [0.0] * 6
        for a in range(3):
            bounds[2 * a] = bounds[2 * a + 1] = center if a == axis else 0.0
        bounds[2 * other[0]], bounds[2 * other[0] + 1] = float(rlo[0]), float(rhi[0])
        bounds[2 * other[1]], bounds[2 * other[1] + 1] = float(rlo[1]), float(rhi[1])
        g = 60
        us = np.linspace(rlo[0], rhi[0], g, endpoint=False) + (rhi[0] - rlo[0]) / g / 2
        vs = np.linspace(rlo[1], rhi[1], g, endpoint=False) + (rhi[1] - rlo[1]) / g / 2
        grid = np.zeros((g * g, 3)); uu, vv = np.meshgrid(us, vs)
        grid[:, axis] = center; grid[:, other[0]] = uu.ravel(); grid[:, other[1]] = vv.ravel()
        extras[f"area{'xyz'[axis]}"] = float((~tm.contains(grid)).mean() * (3 * DX) ** 2)
        probes.append(dict(id=f"area{'xyz'[axis]}", bounds_m=tuple(round(b, 10) for b in bounds), expected=(3 * DX) ** 2 - solid_area, tolerance=1.0, units="m2"))
    return probes, ijk, extras


def deck_text(c, ijk):
    tm = c["tm"]
    v = ",".join(format(x, ".17g") for x in np.ravel(tm.vertices))
    f = ",".join(f"{a + 1},{b + 1},{cc + 1},0" for a, b, cc in tm.faces)
    xb = ",".join(format(x, ".10g") for x in np.ravel(np.column_stack([c["lo_d"], c["hi_d"]])))
    return (f"&HEAD CHID='pilot' /\n&TIME T_END=0.02, DT=0.01 /\n&MESH ID='room', IJK={ijk[0]},{ijk[1]},{ijk[2]}, XB={xb} /\n"
            f"&GEOM ID='g', VERTS={v}, FACES={f} /\n&TAIL /\n")


results = []
for n, c in enumerate(picked):
    row = dict(i=n, solid_volume_m3=round(float(c["tm"].volume), 6), min_dim_m=round(min(c["dims"]), 4), type=c["type"], aligned_share=c["aligned_share"], dims_m=[round(x, 3) for x in c["dims"]], cells=c["cells"], faces=len(c["tm"].faces))
    try:
        probes, ijk, extras = probes_for(c)
        text = deck_text(c, ijk)
        with tempfile.TemporaryDirectory(prefix="cc") as d:
            res = effective_cutcell.certify_cutcell_geometry(text, probes, AuditConfig(solver_evidence_directory=d))
        row["grid_check_area"] = extras
        row["status"] = res.status.value if hasattr(res.status, "value") else str(res.status)
        row["reason"] = (res.reason or "")[:160]
        ms = (res.evidence or {}).get("measurements") or {}
        row["measurements"] = {k: dict(expected=v["expected"], measured=v["measured"], abs_error=v["abs_error"], units=v["units"]) for k, v in ms.items()}
    except Exception as exc:  # pilot: record and continue
        row["status"] = "ERROR"
        row["reason"] = f"{type(exc).__name__}: {exc}"[:200]
    results.append(row)
    print(n, row["type"], "aligned", row["aligned_share"], row["status"], (row.get("reason") or "")[:90], flush=True)
json.dump(results, open(out_path, "w", encoding="utf-8"), indent=1)
print("done", Counter(r["status"] for r in results))
