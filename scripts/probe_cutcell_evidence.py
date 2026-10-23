"""Inspect native FDS evidence availability; never certify cut-cell occupancy."""

import argparse
import hashlib
import json
from pathlib import Path
import struct


def gcf_header(path):
    # FDS-6.11.1 Source/dump.f90:DUMP_CFACES_GEOM, version 2 static header.
    with path.open("rb") as stream:
        def record(size):
            prefix = stream.read(4)
            if len(prefix) != 4 or struct.unpack("<i", prefix)[0] != size:
                raise ValueError("Unsupported/truncated GCF record")
            payload, suffix = stream.read(size), stream.read(4)
            if len(payload) != size or suffix != prefix:
                raise ValueError("GCF record markers differ")
            return payload
        endian = struct.unpack("<i", record(4))[0]
        version = struct.unpack("<i", record(4))[0]
        static = struct.unpack("<3i", record(12))
        time = struct.unpack("<f", record(4))[0]
        vertices, faces, volumes = struct.unpack("<3i", record(12))
        if endian != 1 or version != 2 or static != (0, 0, 1):
            raise ValueError("Unsupported GCF header")
    return {"version": version, "time_s": time, "vertices": vertices,
            "faces": faces, "volumes": volumes, "scope": "SURFACE_HEADER_ONLY"}


def probe(matrix_path, output):
    matrix_path = Path(matrix_path).resolve()
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    report = {"status": "INCONCLUSIVE", "solver_version": "6.11.1", "cases": {},
              "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
              "source_evidence": {
                  "geom_blob_sha": "dda11fa527bc645a767bda29176ec6a3eb3252b0",
                  "debug_export": "Source/geom.f90:5343 DEBUG_SET_CUTCELLS is a compile-time FALSE parameter",
                  "volume_export": "Source/geom.f90:11076-11096 is guarded by DEBUG_SET_CUTCELLS",
                  "surface_export": "Source/dump.f90:5566-5636 DUMP_CFACES_GEOM writes NVOLS=0",
                  "ref": "https://github.com/firemodels/fds/tree/FDS-6.11.1/Source",
              },
              "conclusion": "CURRENT_SUPPORTED_OUTPUTS_INSUFFICIENT_FOR_COMPLETE_CUT_CELL_AUDIT",
              "cut_cell_occupancy": "NOT_VERIFIED", "gas_face_connectivity": "NOT_VERIFIED"}
    for name in ("geom", "geom_multi_surface", "ifc_mep"):
        case = matrix["cases"].get(name)
        if not case:
            continue
        acceptance = json.loads((matrix_path.parent / case["packet"]).read_text(encoding="utf-8"))
        run = acceptance.get("cold_flow", {})
        evidence = run.get("evidence", {})
        directory = evidence.get("directory")
        files = {}
        if directory:
            for path in Path(directory).glob("*"):
                if path.is_file() and path.suffix in (".bingeom", ".gcf", ".ge", ".ge2"):
                    entry = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
                    if path.suffix == ".gcf":
                        entry["header"] = gcf_header(path)
                    files[path.name] = entry
        surface = evidence.get("solver_surface_geometry", {}).get("status", "NOT_RUN")
        report["cases"][name] = {"solver": run.get("status", "NOT_RUN"), "surface_geometry": surface,
            "effective_geometry": acceptance.get("effective_geometry", {}).get("status", "NOT_RUN"),
            "input_sha256": evidence.get("fds_sha256"), "solver_sha256": evidence.get("sha256"), "files": files,
            "debug_volume_files_present": bool(directory and list(Path(directory).glob("*_cutcellCCVAR.dat")))}
        if run.get("status") == "FAIL" or surface == "FAIL":
            report["status"] = "FAIL"
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = probe(args.matrix, args.output)
    print(json.dumps({"status": result["status"], "cases": len(result["cases"]), "conclusion": result["conclusion"]}))
    return 1 if result["status"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
