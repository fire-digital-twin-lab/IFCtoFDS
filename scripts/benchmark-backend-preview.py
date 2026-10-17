"""Measure actual IFC backend preview, without claiming mapping acceptance.

Output is local-only under scripts/out by default. Source files stay immutable.
"""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import psutil
    from ifc_to_fds.application.use_cases.preview_model import preview_model
    from ifc_to_fds.diagnostics import execution_scope
    from ifc_to_fds.geometry.storage import file_hash

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "scripts/out/backend-preview"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    before = file_hash(args.source)
    started = perf_counter()
    with execution_scope(args.output):
        result = preview_model([args.source], args.output)
    result["elapsed_s"] = perf_counter() - started
    result["process_peak_working_set_bytes"] = getattr(
        psutil.Process().memory_info(), "peak_wset", None
    )
    result["source_unchanged"] = before == file_hash(args.source)
    (args.output / "preview-result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("sources", "storeys", "artifacts")
            }
        )
    )
    return 0 if result["source_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
