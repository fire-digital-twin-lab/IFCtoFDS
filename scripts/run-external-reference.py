"""Explicit research acceptance run. Missing external data is a failure to verify."""

import argparse
import json
from pathlib import Path
from ifc_to_fds.validation.golden import resolve_sources
from ifc_to_fds.pipeline import convert, save_artifacts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--source-map", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        paths = resolve_sources(
            args.case, json.loads(Path(args.source_map).read_text(encoding="utf-8"))
        )
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        config.update(profile="research-basement", reference_case=args.case)
        result = convert(paths, config)
        save_artifacts(result, Path(args.output) / "model.fds")
        print(
            json.dumps(
                dict(
                    status=result["status"],
                    mapping_status=result["mapping_status"],
                    simulation_status=result["simulation_status"],
                )
            )
        )
        return {"MAPPING_VERIFIED": 0, "REJECTED": 1, "INCONCLUSIVE": 2}[
            result["status"]
        ]
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"RESEARCH_NOT_RUN: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
