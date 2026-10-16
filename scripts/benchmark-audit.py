"""Run legacy-output audit in a process so the benchmark deadline is enforceable."""

import sys
from pathlib import Path
from ifc_to_fds.pipeline import prepare
from ifc_to_fds.validation.engine import run_independent_validation

model = prepare([sys.argv[1]], {}, reference=True)
report = run_independent_validation(
    model, Path(sys.argv[2]).read_text(encoding="utf-8")
)
Path(sys.argv[3]).write_text(report.model_dump_json(indent=2), encoding="utf-8")
