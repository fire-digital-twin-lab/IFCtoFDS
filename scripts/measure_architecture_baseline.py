"""Measures and records architecture baseline metrics across Python and JavaScript files."""

import json
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "tests/baseline/snapshots/baseline_metrics.json"

JS_TARGETS = [
    "js/app-controller.js",
    "js/viewer/scene-viewer.js",
    "js/ifc/ifc-adapter.js",
    "js/fds/fds-exporter.js",
    "css/app.css",
    "index.html",
]

PY_TARGETS = [
    "ifc_to_fds/validation/engine.py",
    "ifc_to_fds/validation/golden.py",
    "ifc_to_fds/domain/bim/model.py",
    "ifc_to_fds/domain/validation/model.py",
    "ifc_to_fds/application/use_cases/audit_conversion.py",
    "ifc_to_fds/server.py",
]

FIXTURE_TARGETS = [
    "tests/baseline/fixtures/tiny.ifc",
    "tests/baseline/fixtures/opening.ifc",
    "tests/baseline/fixtures/mep.ifc",
    "examples/AC20-FZK-Haus.ifc",
]


def count_lines(path: Path) -> dict:
    if not path.is_file():
        return {"total_lines": 0, "code_lines": 0}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    code_lines = [l for l in lines if l.strip() and not l.strip().startswith(("#", "//", "/*", "*"))]
    return {
        "total_lines": len(lines),
        "code_lines": len(code_lines),
    }


def compute_sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main():
    metrics = {
        "javascript_files": {},
        "python_files": {},
        "fixtures": {},
    }

    print("Measuring JavaScript Targets:")
    for rel in JS_TARGETS:
        p = ROOT / rel
        data = count_lines(p)
        metrics["javascript_files"][rel] = data
        print(f"  {rel:30s}: {data['total_lines']:5d} total lines ({data['code_lines']:5d} code lines)")

    print("\nMeasuring Python Targets:")
    for rel in PY_TARGETS:
        p = ROOT / rel
        data = count_lines(p)
        metrics["python_files"][rel] = data
        print(f"  {rel:50s}: {data['total_lines']:5d} total lines ({data['code_lines']:5d} code lines)")

    print("\nRecording Fixture Checksums:")
    for rel in FIXTURE_TARGETS:
        p = ROOT / rel
        digest = compute_sha256(p)
        metrics["fixtures"][rel] = {"sha256": digest, "size_bytes": p.stat().st_size if p.is_file() else 0}
        print(f"  {rel:35s}: {digest[:16]}... ({metrics['fixtures'][rel]['size_bytes']} bytes)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nBaseline metrics written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
