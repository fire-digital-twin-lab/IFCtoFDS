"""Isolated comparable runs. Failures/timeouts remain in the results."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def measured(command, timeout):
    start = time.perf_counter()
    peak = 0
    with __import__("tempfile").TemporaryFile(mode="w+b") as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=log,
            stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        timed_out = False
        while process.poll() is None:
            try:
                parent = psutil.Process(process.pid)
                peak = max(
                    peak,
                    sum(
                        p.memory_info().rss
                        for p in [parent, *parent.children(recursive=True)]
                        if p.is_running()
                    ),
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if time.perf_counter() - start > timeout:
                from ifc_to_fds.jobs import JobManager

                JobManager._stop(process)
                timed_out = True
                break
            time.sleep(0.05)
        process.wait()
        log.seek(0)
        return dict(
            elapsed_s=time.perf_counter() - start,
            peak_rss_bytes=peak,
            exit_code=process.returncode,
            timed_out=timed_out,
            log=log.read().decode("utf-8", errors="replace")[-10000:],
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        nargs="+",
        default=[str(p) for p in (ROOT / "examples").glob("*.ifc")],
    )
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output", default="benchmark-results")
    args = parser.parse_args()
    if args.repeat < 1 or args.warmup < 0 or args.timeout <= 0:
        parser.error("repeat/timeout must be positive; warmup must be nonnegative")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for model in args.models:
        source = Path(model).resolve()
        for method in ("quick", "all_geom", "mixed"):
            for run in range(-args.warmup, args.repeat):
                directory = output / (source.stem + "-" + method + "-" + str(run))
                directory.mkdir(parents=True, exist_ok=True)
                fds = directory / "model.fds"
                if method == "quick":
                    command = [
                        "node",
                        "scripts/benchmark-native.js",
                        str(source),
                        str(fds),
                    ]
                else:
                    command = [
                        sys.executable,
                        "-m",
                        "ifc_to_fds",
                        "convert",
                        str(source),
                        "-o",
                        str(fds),
                    ]
                    if method == "all_geom":
                        command.append("--all-geom")
                row = measured(command, args.timeout)
                row.update(
                    model=source.name,
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    method=method,
                    run=run,
                    warmup=run < 0,
                    output_bytes=fds.stat().st_size if fds.exists() else None,
                )
                if method == "quick" and fds.exists():
                    quick_report = directory / "quick_audit.json"
                    row["audit_execution"] = measured(
                        [
                            sys.executable,
                            "scripts/benchmark-audit.py",
                            str(source),
                            str(fds),
                            str(quick_report),
                        ],
                        args.timeout,
                    )
                    if quick_report.exists():
                        row["audit"] = json.loads(
                            quick_report.read_text(encoding="utf-8")
                        )
                elif (directory / "model_acceptance_report.json").exists():
                    row["audit"] = json.loads(
                        (directory / "model_acceptance_report.json").read_text(
                            encoding="utf-8"
                        )
                    )
                timing_path = directory / "model_timings.json"
                if timing_path.exists():
                    row["stage_timings"] = json.loads(
                        timing_path.read_text(encoding="utf-8")
                    )
                rows.append(row)
                result = dict(
                    platform=platform.platform(),
                    python=sys.version,
                    rows=rows,
                    commit=subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], text=True
                    ).strip(),
                    dirty=bool(
                        subprocess.check_output(
                            ["git", "diff", "--name-only"], text=True
                        ).strip()
                    ),
                    warmups=args.warmup,
                    measured_repeats=args.repeat,
                    method_limits="Quick retains legacy representation policy; compare fidelity and coverage, not time alone",
                )
                (output / "results.json").write_text(
                    json.dumps(result, indent=2), encoding="utf-8"
                )
                print(
                    source.name,
                    method,
                    run,
                    row["exit_code"],
                    round(row["elapsed_s"], 2),
                    flush=True,
                )


if __name__ == "__main__":
    main()
