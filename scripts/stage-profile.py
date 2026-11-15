"""Profile one conversion and attribute time to named pipeline buckets.

    python scripts/stage-profile.py model.ifc [-o profile.json] [--cache DIR] [--top 15]

Prints stage timings (from the pipeline) and cProfile cumulative time per bucket.
Bucket time is the cumulative time of the outermost matching function, so nested
matches are not double counted. Output holds only totals and function names,
never element names or GUIDs.
"""

import argparse
import cProfile
import json
import os
import pstats
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("IFCFDS_SOLVER_AUTODISCOVERY", "0")

# (bucket, file suffix, function name); first match wins for the outermost call.
BUCKETS = [
    ("native_tessellation", "ifcopenshell", "get"),
    ("native_tessellation", "ifcopenshell", "create_shape"),
    ("component_union", "component_union.py", "fuse_overlapping_components"),
    ("normalization", "normalization.py", "normalize_source_mesh"),
    ("self_intersection", "mesh.py", "self_intersection_evidence"),
    ("mesh_quality", "mesh.py", "inspect_mesh_quality"),
    ("compare_solids", "metrics.py", "compare_solids"),
    ("passage_metrics", "metrics.py", "passage_metrics"),
    ("opening_residual", "metrics.py", "opening_residual"),
    ("air_path", "air_path.py", "check"),
    ("package_audit", "package.py", "audit_package"),
    ("package_write", "storage.py", "write_package"),
    ("file_hash", "storage.py", "file_hash"),
    ("mapping_serialize", "exporter.py", "serialize_fds"),
    ("parse_fds", "parser.py", "parse_fds"),
]


def bucket_times(stats):
    """Cumulative seconds per bucket, counting only calls not nested in the same bucket."""
    out = {}
    for (path, _, name), (_, calls, _, cumulative, callers) in stats.stats.items():
        for bucket, suffix, function in BUCKETS:
            if name == function and path.replace("\\", "/").endswith(suffix) or (
                suffix == "ifcopenshell" and name == function and "ifcopenshell" in path
            ):
                inner = sum(
                    c[3] for k, c in callers.items() if any(
                        b == bucket and k[2] == f and k[0].replace("\\", "/").endswith(s)
                        for b, s, f in BUCKETS
                    )
                )
                out[bucket] = out.get(bucket, 0.0) + max(0.0, cumulative - inner)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ifc")
    parser.add_argument("-o", "--output")
    parser.add_argument("--cache", help="geometry cache dir (default: a fresh temp dir = cold)")
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()
    cache = args.cache or tempfile.mkdtemp(prefix="stage-profile-cache-")
    os.environ["IFCFDS_GEOMETRY_CACHE"] = cache
    from ifc_to_fds.pipeline import convert

    profile = cProfile.Profile()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="stage-profile-") as work:
        profile.enable()
        result = convert([args.ifc], output_directory=work)
        profile.disable()
    wall = time.perf_counter() - started
    stats = pstats.Stats(profile)
    buckets = bucket_times(stats)
    rows = sorted(
        ((tt, ct, nc, f"{os.path.basename(p)}:{n}") for (p, _, n), (_, nc, tt, ct, _) in stats.stats.items()),
        reverse=True,
    )
    data = dict(
        source=Path(args.ifc).name if os.environ.get("STAGE_PROFILE_KEEP_NAME") else "model.ifc",
        status=result["status"],
        wall_profiled_s=round(wall, 1),
        stage_timings_s={k: round(v, 2) for k, v in result["timings"].items() if k.endswith("_s")},
        bucket_cumulative_s={k: round(v, 1) for k, v in sorted(buckets.items(), key=lambda kv: -kv[1])},
        top_self_time=[dict(function=f, self_s=round(tt, 2), cumulative_s=round(ct, 2), calls=nc) for tt, ct, nc, f in rows[: args.top]],
    )
    print(json.dumps(data, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
