"""Run `ifc_to_fds convert` on every file listed in a public-ifc-fetch manifest, one process per file, and summarise the outcomes.

    python -I scripts/public-ifc-run.py --root <fetch dir> --runs <output dir> [--min-mb 0] [--max-mb 15] [--only text] [--timeout 900]

Per file it records the exit code, wall seconds, peak resident memory of the whole process tree, the reason a run was killed
(timeout or memory guard) and the verdict read from the acceptance report. The output directory is created per file with a
fresh geometry cache. Results are appended to <runs>/results.jsonl, so an interrupted run resumes where it stopped.

Outcome classes: REPORT:<status> (a report was written), REFUSED (exit code 3, a controlled "Conversion/audit error"),
TIMEOUT, MEMORY_GUARD, TRACEBACK (an uncaught exception) and EXIT<n>. Needs psutil (installed with the project).
Run it with `python -I` from a directory that does not contain downloaded data; paths are passed as arguments only.
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys
import time

import psutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_inside(path, base):
    """True when path is base or below it; paths on different drives are never inside."""
    path, base = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(base))
    try:
        return os.path.commonpath([path, base]) == base
    except ValueError:  # different drives on Windows
        return False


def tree_rss(process):
    total = 0
    try:
        for p in [process] + process.children(recursive=True):
            try:
                total += p.memory_info().rss
            except psutil.Error:
                pass
    except psutil.Error:
        pass
    return total


def kill_tree(process):
    try:
        for child in process.children(recursive=True):
            child.kill()
        process.kill()
    except psutil.Error:
        pass


def step_schema(path):
    with open(path, "rb") as handle:
        match = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", handle.read(6000).decode("latin-1", "replace"))
    return match.group(1) if match else "?"


def read_report(out_dir):
    path = os.path.join(out_dir, "model_acceptance_report.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    gates = {name: dict(status=v.get("status"), reason=(v.get("reason") or "")[:140])
             for name, v in (report.get("gates") or {}).items() if v.get("status") not in ("PASS", "NOT_APPLICABLE")}
    return dict(status=report.get("status"), mapping=report.get("mapping_status"), simulation=report.get("simulation_status"),
                elements=dict(collections.Counter((report.get("element_statuses") or {}).values())),
                findings=dict(collections.Counter(f.get("severity") for f in report.get("findings", []))), gates=gates)


def outcome(row):
    if row["kill"]:
        return row["kill"]
    if row["traceback"]:
        return "TRACEBACK"
    if row.get("status"):
        return "REPORT:" + row["status"]
    return "REFUSED" if row["exit"] == 3 else f"EXIT{row['exit']}"


def run_one(ifc, out_dir, python, timeout, mem_guard):
    os.makedirs(out_dir, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1", IFCFDS_GEOMETRY_CACHE=os.path.join(out_dir, "cache"))
    log_path = os.path.join(out_dir, "run.log")
    started, peak, reason = time.time(), 0, None
    with open(log_path, "wb") as log:
        proc = subprocess.Popen([python, "-I", "-m", "ifc_to_fds", "convert", ifc, "-o", os.path.join(out_dir, "model.fds")],
                                stdout=log, stderr=subprocess.STDOUT, env=env, cwd=REPO)
        watched = psutil.Process(proc.pid)
        while proc.poll() is None:
            peak = max(peak, tree_rss(watched))
            if peak > mem_guard:
                reason = "MEMORY_GUARD"
            elif time.time() - started > timeout:
                reason = "TIMEOUT"
            if reason:
                kill_tree(watched)
                break
            time.sleep(0.4)
        proc.wait()
    with open(log_path, "rb") as handle:
        text = handle.read().decode("utf-8", "replace")
    lines = [line for line in text.splitlines() if line.strip() and "Warning" not in line and "center_mass" not in line]
    return dict(exit=proc.returncode, seconds=round(time.time() - started, 1), peak_rss_mb=round(peak / 1048576), kill=reason,
                traceback="Traceback (most recent call last)" in text, tail=[line[:220] for line in lines[-3:]], **read_report(out_dir))


def summarise(rows):
    print("\n== outcomes:", dict(collections.Counter(outcome(r) for r in rows)))
    refused = collections.Counter(re.sub(r"\d[\d,]*", "N", re.sub(r"\s+", " ", " ".join(r["tail"]))[:150]) for r in rows if outcome(r) == "REFUSED")
    for message, count in refused.most_common():
        print(f"   REFUSED x{count}: {message}")
    for r in sorted(rows, key=lambda r: -r["seconds"])[:5]:
        print(f"   slowest: {r['seconds']:7.1f}s {r['peak_rss_mb']:5d} MB  {r['id']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, help="directory written by public-ifc-fetch.py (contains manifest.json)")
    parser.add_argument("--runs", required=True, help="output directory (outside the repository)")
    parser.add_argument("--min-mb", type=float, default=0)
    parser.add_argument("--max-mb", type=float, default=15)
    parser.add_argument("--only", default="", help="only files whose manifest key contains this text")
    parser.add_argument("--timeout", type=float, default=900, help="seconds per file")
    parser.add_argument("--mem-guard-mb", type=int, default=5500, help="kill a run whose process tree exceeds this resident memory")
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)
    runs = os.path.abspath(args.runs)
    if is_inside(runs, REPO):
        sys.exit("--runs must be outside the repository")
    os.makedirs(runs, exist_ok=True)
    results_path = os.path.join(runs, "results.jsonl")
    rows = [json.loads(line) for line in open(results_path, encoding="utf-8")] if os.path.exists(results_path) else []
    done = {r["id"] for r in rows}
    with open(os.path.join(args.root, "manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    todo = sorted((v["bytes"], k) for k, v in manifest.items() if args.min_mb <= v["bytes"] / 1048576 < args.max_mb and args.only in k)
    for size, key in todo:
        if key in done:
            continue
        ifc = os.path.join(args.root, *key.split("/"))
        row = dict(id=key, mb=round(size / 1048576, 2), schema=step_schema(ifc))
        out_dir = os.path.join(runs, re.sub(r"[^A-Za-z0-9._-]+", "_", key)[:90])
        row.update(run_one(ifc, out_dir, args.python, args.timeout, args.mem_guard_mb << 20))
        rows.append(row)
        with open(results_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{outcome(row):22s} {row['seconds']:7.1f}s {row['peak_rss_mb']:5d}MB {row['schema'][:10]:10s} {key}", flush=True)
    summarise([r for r in rows if args.min_mb <= r["mb"] < args.max_mb and args.only in r["id"]])


if __name__ == "__main__":
    main()
