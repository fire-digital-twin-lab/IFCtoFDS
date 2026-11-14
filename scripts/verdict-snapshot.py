"""Record per-element audit outcomes and stage timings for one IFC.

Run before and after a speed change; `--compare` shows any element whose status
or witness kind changed. Timings are printed but never compared.

    python scripts/verdict-snapshot.py examples/AC20-FZK-Haus.ifc -o docs/evidence/production-roadmap/baseline-fzk.json
    python scripts/verdict-snapshot.py examples/AC20-FZK-Haus.ifc --compare docs/evidence/production-roadmap/baseline-fzk.json
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("IFCFDS_SOLVER_AUTODISCOVERY", "0")

from ifc_to_fds.pipeline import convert  # noqa: E402


def snapshot(ifc: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="verdict-snapshot-") as work:
        started = time.perf_counter()
        result = convert([ifc], output_directory=work)
        wall = time.perf_counter() - started
    manifest = result.get("manifest") or {}
    report = result.get("report") or {}
    statuses = report.get("element_statuses") or {}
    witnesses = {}
    for key, value in (report.get("metrics") or {}).items():
        if isinstance(value, dict) and "self_intersection" in value:
            witnesses[key] = (value["self_intersection"].get("witness") or {}).get("kind")
    findings = {}
    for finding in report.get("findings") or []:
        findings[finding.get("category", "?")] = findings.get(finding.get("category", "?"), 0) + 1
    return dict(
        source=Path(ifc).name,
        status=result.get("status"),
        element_statuses=statuses,
        witness_kinds=witnesses,
        findings_by_gate=findings,
        records=len(manifest.get("records", [])),
        wall_s=round(wall, 2),
        stage_timings_s={k: round(v, 2) for k, v in (result.get("timings") or {}).items() if k.endswith("_s")},
    )


def compare(old: dict, new: dict) -> int:
    diffs = 0
    for field in ("status",):
        if old[field] != new[field]:
            print(f"{field}: {old[field]} -> {new[field]}")
            diffs += 1
    for field in ("element_statuses", "witness_kinds", "findings_by_gate"):
        for key in sorted(set(old[field]) | set(new[field])):
            if old[field].get(key) != new[field].get(key):
                print(f"{field}[{key}]: {old[field].get(key)} -> {new[field].get(key)}")
                diffs += 1
    print(f"wall: {old['wall_s']}s -> {new['wall_s']}s; differences: {diffs}")
    return 1 if diffs else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ifc")
    parser.add_argument("-o", "--output")
    parser.add_argument("--compare")
    args = parser.parse_args()
    data = snapshot(args.ifc)
    if args.output:
        Path(args.output).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {args.output}: status={data['status']} wall={data['wall_s']}s")
    if args.compare:
        return compare(json.loads(Path(args.compare).read_text(encoding="utf-8")), data)
    if not args.output:
        print(json.dumps(data, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
