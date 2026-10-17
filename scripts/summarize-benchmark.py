"""Summarize every benchmark outcome, including warmups, failures and timeouts."""

import argparse
import hashlib
import json
import time
from pathlib import Path


def summarize(before, after, output):
    result = {
        "status": "RUNNING",
        "performance_conclusion": "NO_SPEEDUP_CLAIM",
        "revisions": {},
    }
    for label, root in (("before", before), ("after", after)):
        path = Path(root) / "results.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        rows = data.get("rows", [])
        result["revisions"][label] = dict(
            result_file=str(path.resolve()),
            result_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            if path.exists()
            else None,
            runs_recorded=len(rows),
            expected_runs=4,
            measured_timeouts=sum(not r["warmup"] and r["timeout"] for r in rows),
            measured_failures=sum(
                not r["warmup"] and not r["timeout"] and r["exit_code"] != 0
                for r in rows
            ),
            measured_successes=sum(
                not r["warmup"] and not r["timeout"] and r["exit_code"] == 0
                for r in rows
            ),
            timeout_s=data.get("timeout_s", 1800),
            configuration=data.get("configuration"),
            rows=rows,
        )
    if all(r["runs_recorded"] == 4 for r in result["revisions"].values()):
        result["status"] = "MEASUREMENTS_FINISHED"
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        "# Benchmark evidence",
        "",
        "Status: " + result["status"],
        "",
        "One warmup and three measured runs per revision. All outcomes are retained. No speedup or research acceptance is claimed.",
        "",
        "| Revision | Run | Warmup | Seconds | Peak RSS MB | Timeout | Exit | Result bytes |",
        "|---|---:|---|---:|---:|---|---:|---:|",
    ]
    for label, revision in result["revisions"].items():
        for row in revision["rows"]:
            lines.append(
                f"| {label} | {row['run']} | {row['warmup']} | {row['elapsed_s']:.3f} | {row['peak_rss_bytes'] / 1e6:.2f} | {row['timeout']} | {row['exit_code']} | {row.get('result_bytes', 'unavailable')} |"
            )
    lines += [
        "",
        "Raw result paths, checksums, configuration, failures and stage evidence are recorded in the JSON companion. Unavailable metrics are not inferred.",
    ]
    target.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            state = summarize(args.before, args.after, args.output)["status"]
            if not args.watch or state == "MEASUREMENTS_FINISHED":
                print(state)
                break
        except (OSError, json.JSONDecodeError):
            if not args.watch:
                raise
        time.sleep(5)
