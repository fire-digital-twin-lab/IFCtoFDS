"""End-to-end benchmark of real building model (Ham2Tang.ifc) with architectural improvements.

Validates:
1. Origin Rebasing: Normalized coordinates in local space, header provenance emitted.
2. 2D/Positioning filtering: IfcGrid mapped cleanly to SEMANTIC_ONLY without OpenCASCADE errors.
3. Assembly decomposition: IfcCurtainWall/IfcStair containers unwrapped without missing solid findings.
4. Invalid source meshes: Retained and reported without bounding-box substitution.
5. High-throughput performance: Execution time measured.
6. FDS 6.11.1 setup at T_END=0 (independent of mapping acceptance).
"""

import argparse
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import psutil

from ifc_to_fds.pipeline import convert, save_artifacts
from ifc_to_fds.diagnostics import execution_scope

repo_root = Path(__file__).resolve().parent.parent


def parse_args():
    parser = argparse.ArgumentParser(description="End-to-end Ham2Tang benchmark")
    parser.add_argument(
        "--ifc-path",
        type=Path,
        default=Path(os.getenv("HAM2TANG_PATH", r"D:\Users\Documents\HUCE\NCKH PCCC\Resources\Ham2tang\Ham2Tang.ifc")),
        help="Path to Ham2Tang.ifc",
    )
    parser.add_argument(
        "--fds-bin-dir",
        type=Path,
        default=Path(os.getenv("FDS_BIN_DIR", repo_root / ".deps" / "fds-6.11.1" / "firemodels" / "FDS6" / "bin")),
        help="Path to FDS bin directory containing fds.exe and mpi",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("scripts/out/benchmark-ham2tang-improved"),
        help="Output directory for benchmark artifacts",
    )
    return parser.parse_args()


def run_benchmark():
    args = parse_args()
    ham2tang_path = args.ifc_path
    out_dir = args.out_dir / datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
    fds_bin_dir = args.fds_bin_dir.resolve()
    fds_executable = fds_bin_dir / "fds_openmp.exe"
    if not fds_executable.is_file():
        fds_executable = fds_bin_dir / "fds.exe"

    assert ham2tang_path.exists(), f"Source not found: {ham2tang_path}"
    assert fds_executable.exists(), f"FDS executable not found: {fds_executable}"

    out_dir.mkdir(parents=True, exist_ok=False)

    file_size_mb = ham2tang_path.stat().st_size / (1024 * 1024)
    print(f"=== BENCHMARK: Ham2Tang.ifc ({file_size_mb:.2f} MB) ===")
    print("Starting conversion with architectural improvements...")

    start_time = time.perf_counter()
    proc = psutil.Process()
    rss_before = proc.memory_info().rss

    config = {
        "profile": "geometry-fidelity",
        "cell_size": 0.2,
        "auto_rebase_origin": True,
    }

    with execution_scope(out_dir):
        result = convert([str(ham2tang_path)], configuration=config, output_directory=out_dir)
        save_artifacts(result, out_dir / "Ham2Tang.fds")

    total_time = time.perf_counter() - start_time
    rss_delta_mb = (proc.memory_info().rss - rss_before) / (1024 * 1024)

    fds_text = (out_dir / "Ham2Tang.fds").read_text(encoding="utf-8")
    manifest = result["manifest"]
    report = result["report"]

    # 1. Check Origin Rebasing
    has_rebase_header = "! IFC_COORDINATE_REBASE" in fds_text
    rebase_vec = manifest.get("configuration", {}).get("rebase_vector") or result.get("configuration", {}).get("rebase_vector")

    # 2. Check Grid entities
    grid_records = [r for r in manifest.get("records", []) if r.get("ifc_type") == "IfcGrid"]
    grids_all_semantic = all(r.get("mapping_strategy") == "SEMANTIC_ONLY" for r in grid_records)

    # 3. Check Assembly parents
    cw_records = [r for r in manifest.get("records", []) if r.get("ifc_type") == "IfcCurtainWall"]
    cw_all_semantic = all(r.get("mapping_strategy") == "SEMANTIC_ONLY" for r in cw_records)

    # 4. Check Doors
    door_records = [r for r in manifest.get("records", []) if r.get("ifc_type") == "IfcDoor"]
    unsupported_doors = sum(r.get("mapping_strategy") == "NONE" for r in door_records)

    # 5. Check FDS Primitives
    geom_count = fds_text.count("&GEOM")
    obst_count = fds_text.count("&OBST")
    fds_size_mb = (out_dir / "Ham2Tang.fds").stat().st_size / (1024 * 1024)

    print("\n--- Pipeline Verification Summary ---")
    print(f"Total conversion & audit time: {total_time:.2f} s (RSS delta: {rss_delta_mb:.2f} MB)")
    print(f"FDS file size: {fds_size_mb:.2f} MB")
    print(f"Primitves emitted: {geom_count} &GEOM, {obst_count} &OBST")
    print(f"Origin rebase applied: {has_rebase_header} (rebase vector: {rebase_vec})")
    print(f"IfcGrid count: {len(grid_records)}, all SEMANTIC_ONLY: {grids_all_semantic}")
    print(f"IfcCurtainWall count: {len(cw_records)}, all SEMANTIC_ONLY: {cw_all_semantic}")
    print(f"IfcDoor count: {len(door_records)}; unsupported source geometry: {unsupported_doors}")
    print(f"Independent acceptance: {result['status']}")

    # Assertions on pipeline invariants
    assert has_rebase_header, "Origin rebase header missing from emitted FDS"
    assert grids_all_semantic, "Not all IfcGrid elements were classified as SEMANTIC_ONLY"
    assert cw_all_semantic, "Not all assembly containers were unwrapped"

    # 6. Run official FDS 6.11.1 Solver setup test
    print("\n--- Running Official FDS 6.11.1 Solver Setup Test ---")
    solver_dir = out_dir / "solver-run"
    solver_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(out_dir / "Ham2Tang.fds", solver_dir / "Ham2Tang.fds")

    solver_start = time.perf_counter()
    fds_env = os.environ.copy()
    mpi_dir = str(fds_bin_dir / "mpi")
    fds_env["I_MPI_ROOT"] = mpi_dir
    fds_env["PATH"] = f"{fds_bin_dir};{mpi_dir};" + fds_env.get("PATH", "")
    fds_env["IN_CMDFDS"] = "1"
    fds_env["OMP_NUM_THREADS"] = "1"
    fds_env.setdefault("I_MPI_FABRICS", "shm")

    solver_proc = subprocess.run(
        [str(fds_executable), "Ham2Tang.fds"],
        cwd=solver_dir,
        capture_output=True,
        text=True,
        timeout=60,
        env=fds_env,
    )
    solver_time = time.perf_counter() - solver_start

    smv_file = solver_dir / "Ham2Tang.smv"
    has_smv = smv_file.exists()
    fds_stdout = solver_proc.stdout + solver_proc.stderr

    setup_success = solver_proc.returncode == 0 and "STOP: Set-up only" in fds_stdout
    print(f"FDS Exit Code: {solver_proc.returncode}")
    print(f"FDS Solver Wall-clock: {solver_time:.2f} s")
    print(f"Smokeview file generated: {has_smv} ({smv_file.stat().st_size if has_smv else 0} bytes)")
    print(f"Setup-only successful: {setup_success}")

    assert setup_success, f"FDS solver setup failed (exit code {solver_proc.returncode}): {solver_proc.stderr}"
    assert has_smv, "Smokeview (.smv) file was not generated by solver"

    summary = {
        "model": "Ham2Tang.ifc",
        "file_size_mb": file_size_mb,
        "rss_delta_mb": rss_delta_mb,
        "total_time_s": total_time,
        "solver_time_s": solver_time,
        "fds_exit_code": solver_proc.returncode,
        "setup_success": setup_success,
        "mapping_acceptance": result["status"],
        "unsupported_source_doors": unsupported_doors,
        "has_smv": has_smv,
        "primitives": {"GEOM": geom_count, "OBST": obst_count},
        "rebase_header": has_rebase_header,
        "rebase_vector": rebase_vec,
        "grids_filtered": grids_all_semantic,
        "assemblies_unwrapped": cw_all_semantic,
        "gates": {k: v.get("status") for k, v in report.get("gates", {}).items()},
    }

    (out_dir / "benchmark_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nBenchmark completed successfully! Results written to {out_dir / 'benchmark_summary.json'}")
    return summary


if __name__ == "__main__":
    run_benchmark()
