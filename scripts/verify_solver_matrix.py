"""Run real pinned-FDS checks and retain separate initialization/effective gates.

python -m scripts.verify_solver_matrix --solver PATH --output scripts/out/solver-matrix
"""

import argparse
import json
from pathlib import Path

from ifc_to_fds.domain.validation import AuditConfig
from ifc_to_fds.modules.verification.api import solver_gates
from tests.support.solver_cases import solver_cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = {}
    unexpected = []
    for name, text in solver_cases().items():
        directory = args.output / name
        solver, effective = solver_gates(
            text,
            AuditConfig(
                solver_executable=args.solver,
                solver_evidence_directory=str(directory),
            ),
        )
        results[name] = {
            "solver": solver.model_dump(mode="json"),
            "effective_geometry": effective.model_dump(mode="json"),
        }
        expected_solver = "FAIL" if name == "invalid_geom" else "PASS"
        expected_effective = (
            "PASS" if name in ("obst", "hole", "vent", "multi_mesh") else "INCONCLUSIVE"
        )
        matched = (
            solver.status.value == expected_solver
            and effective.status.value == expected_effective
        )
        results[name]["expected"] = {
            "solver": expected_solver,
            "effective_geometry": expected_effective,
        }
        results[name]["matches_expected"] = matched
        if not matched:
            unexpected.append(name)
        (args.output / "results.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        print(name, solver.status.value, effective.status.value, flush=True)
    if unexpected:
        raise SystemExit(
            "Unexpected solver/effective verdicts: " + ", ".join(unexpected)
        )


if __name__ == "__main__":
    main()
