"""Run inside the solver image (`docker build --target solver`) under the production security profile.

FDS 6.11.1 must set up on a small deck and the effective-geometry gate must read its SMV (plan M5.4). Exit 0 only
when both gates pass.
"""

import os
import sys
import tempfile

from ifc_to_fds.validation.acceptance import AuditConfig
from ifc_to_fds.validation.solver import solver_gates

DECK = "\n".join([
    "&HEAD CHID='probe' /", "&MESH IJK=10,10,10, XB=0,2,0,2,0,2 /", "&TIME T_END=0 /", "&SURF ID='S', COLOR='RED' /",
    "&OBST ID='O1', XB=0.52,1.08,0.52,1.48,0,1 /",
    "&VENT ID='V_TOP', XB=0.52,1.08,0.52,1.48,1,1, SURF_ID='S' /", "&TAIL /", "",
])


def main() -> int:
    with tempfile.TemporaryDirectory(dir=sys.argv[1] if len(sys.argv) > 1 else None) as evidence:
        solver, effective = solver_gates(
            DECK, AuditConfig(solver_executable=os.environ["IFCFDS_SOLVER"], solver_evidence_directory=evidence)
        )
    print(f"solver={solver.status} effective_geometry={effective.status}: {effective.reason}")
    return 0 if solver.status == "PASS" and effective.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
