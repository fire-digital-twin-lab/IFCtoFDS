"""Instrumentation harness for benchmarking large IFC model conversion and validation stages.

Measures Peak RSS (MB), triangle counts, and per-stage timings across all six
Verified Core pipeline stages. Outputs structured telemetry to scripts/out/benchmarks/.
"""

import argparse
import json
from pathlib import Path
from time import perf_counter

try:
    import psutil
except ImportError:
    psutil = None

from ifc_to_fds.pipeline import convert, save_artifacts


def get_peak_rss_mb() -> float:
    if psutil is not None:
        info = psutil.Process().memory_info()
        peak_bytes = getattr(info, "peak_wset", None)
        if peak_bytes is not None:
            return peak_bytes / (1024 * 1024)
        try:
            import importlib
            import sys
            res_mod = importlib.import_module("resource")
            get_usage = getattr(res_mod, "getrusage", None)
            rusage_self = getattr(res_mod, "RUSAGE_SELF", 0)
            if get_usage is not None:
                ru_maxrss = get_usage(rusage_self).ru_maxrss
                return (ru_maxrss / 1024.0) if sys.platform != "darwin" else (ru_maxrss / (1024 * 1024))
        except (ImportError, AttributeError):
            pass
        return info.rss / (1024 * 1024)
    return 0.0


def benchmark_model(ifc_path: str, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    start_rss = get_peak_rss_mb()
    t0 = perf_counter()

    print(f"[*] Starting conversion benchmark for: {ifc_path}")
    print(f"    Initial RSS: {start_rss:.2f} MB")

    result = convert([ifc_path], output_directory=output_dir)
    save_artifacts(result, output_dir / "model.fds")

    total_time = perf_counter() - t0
    peak_rss = get_peak_rss_mb()

    manifest = result.get("manifest") or {}
    timings = result.get("timings") or {}
    elements_count = (
        manifest.get("total_elements_accounted")
        or len(manifest.get("records", []))
        or len(result.get("inventory", {}).get("elements", []))
        or 0
    )

    summary = {
        "source": ifc_path,
        "total_time_seconds": round(total_time, 3),
        "peak_rss_mb": round(peak_rss, 2),
        "initial_rss_mb": round(start_rss, 2),
        "rss_growth_mb": round(max(0.0, peak_rss - start_rss), 2),
        "status": result.get("status"),
        "mapping_status": result.get("mapping_status"),
        "simulation_status": result.get("simulation_status"),
        "elements_count": elements_count,
        "primitives_emitted": manifest.get("total_primitives_emitted", 0),
        "stage_timings": timings,
    }

    report_path = output_dir / "benchmark-summary.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[✓] Benchmark completed in {total_time:.2f}s | Peak RSS: {peak_rss:.2f} MB")
    print(f"    Summary written to: {report_path}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Benchmark IFC to FDS conversion pipeline.")
    parser.add_argument("--source", default="examples/AC20-FZK-Haus.ifc", help="Path to source IFC file.")
    parser.add_argument("--output", default="scripts/out/benchmarks", help="Output directory for telemetry.")
    args = parser.parse_args()

    benchmark_model(args.source, Path(args.output))


if __name__ == "__main__":
    main()
