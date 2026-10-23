"""Prepare reproducible solver/editor cases without attesting PyroSim execution.

Run with python -m scripts.prepare_verification_matrix --output NEW_DIRECTORY.
The synthetic FDS cases deliberately have no independent IFC mapping verdict.
"""

import argparse
import hashlib
import json
from pathlib import Path

from ifc_to_fds.modules.verification.api import verification_capabilities
from scripts.prepare_pyrosim_acceptance import main as prepare_packet

ROOT = Path(__file__).resolve().parents[1]
CASES = ("obst", "hole", "vent", "multi_mesh", "geom", "geom_multi_surface", "ifc_box", "ifc_mep")


def prepare_matrix(output, names, solver=None, duration=1.0):
    from tests.support.solver_cases import solver_cases

    names = list(dict.fromkeys(names))
    if not names or any(name not in CASES for name in names):
        raise ValueError("Select at least one known acceptance case")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    summary = {"scope": "STATIC_VERIFICATION_AND_EDITOR_ACCEPTANCE_MATRIX",
               "capabilities": verification_capabilities(), "cases": {},
               "pyrosim_execution": "NOT_RUN", "simulation": "NOT_VERIFIED"}
    authored = solver_cases()
    authored["geom_multi_surface"] = (
        authored["geom"].replace("&GEOM", "&SURF ID='other' /\n&GEOM")
        .replace("SURF_ID='solid'", "SURF_ID='solid','other'")
        .replace("1,4,3,1", "1,4,3,2")
    )
    for name in names:
        directory = output / name
        directory.mkdir()
        source = directory / (name + ".fds")
        arguments = [str(source), "--output", str(directory / "packet"),
                     "--duration", str(duration), "--require-ready"]
        origin = "AUTHORED_FDS_FIXTURE_NO_IFC_MAPPING_CLAIM"
        if name.startswith("ifc_"):
            from ifc_to_fds.pipeline import convert, save_artifacts

            if name == "ifc_box":
                ifc = ROOT / "tests/browser/box.ifc"
            else:
                from tests.support.mep_geometry import create_mep_geometry_ifc

                ifc = directory / "authored-mep-fire.ifc"
                create_mep_geometry_ifc(ifc)
            result = convert([ifc], {"profile": "geometry-fidelity"},
                             output_directory=directory / "conversion")
            save_artifacts(result, source)
            origin = "AUTHORED_IFC_WITH_INDEPENDENT_MAPPING_AUDIT"
            arguments += ["--ifc", str(ifc), "--manifest", str(source.with_name(source.stem + "_manifest.json")),
                          "--geometry-package", str(source.with_name(source.stem + "_geometry.json"))]
        else:
            source.write_bytes(authored[name].encode("utf-8"))
        if solver:
            arguments += ["--solver", str(solver)]
        exit_code = prepare_packet(arguments)
        report = json.loads((directory / "packet/acceptance.json").read_text(encoding="utf-8"))
        gates = {key: report.get(key, {}).get("status", "NOT_RUN") for key in (
            "syntax", "mapping", "setup_solver", "cold_flow", "effective_geometry",
            "roundtrip_geometry", "roundtrip_solver", "pyrosim_import", "verification")}
        summary["cases"][name] = {
            "origin": origin, "source": str(source.relative_to(output)),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "packet": str((directory / "packet/acceptance.json").relative_to(output)),
            "exit_code": exit_code, "gates": gates,
        }
    all_gates = [state for case in summary["cases"].values() for state in case["gates"].values()]
    summary["status"] = "FAIL" if "FAIL" in all_gates else (
        "PASS" if all(c["gates"]["verification"] == "PASS" for c in summary["cases"].values()) else "INCONCLUSIVE")
    (output / "matrix.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing output is never overwritten")
    parser.add_argument("--case", choices=CASES, action="append", dest="cases")
    parser.add_argument("--solver", type=Path)
    parser.add_argument("--duration", type=float, default=1.0)
    args = parser.parse_args(argv)
    result = prepare_matrix(args.output, args.cases or CASES, args.solver, args.duration)
    print(json.dumps({"status": result["status"], "cases": len(result["cases"])}))
    return 1 if result["status"] == "FAIL" else 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
