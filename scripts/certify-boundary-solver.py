"""Create evidence for the narrow structural OBST boundary policy."""

import argparse
from ifc_to_fds.validation.boundary_fixtures import certify

p = argparse.ArgumentParser()
p.add_argument("--solver", required=True)
p.add_argument("--output", required=True)
args = p.parse_args()
path, passed = certify(args.solver, args.output)
print(path)
raise SystemExit(0 if passed else 1)
