"""Inspect a specific IFC host and persist source/kernel opening evidence."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ifc_to_fds.geometry.diagnostics import inspect_host_openings

parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("--host-step", type=int, required=True)
parser.add_argument("-o", "--output", type=Path, required=True)
args = parser.parse_args()
evidence = inspect_host_openings(args.source, args.host_step)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print(json.dumps(dict(output=str(args.output), source_sha256=evidence["source_sha256"],
                      errors=len(evidence["errors"]), elapsed_s=evidence["elapsed_s"])))
