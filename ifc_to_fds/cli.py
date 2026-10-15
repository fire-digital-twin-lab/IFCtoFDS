"""Command Line Interface for Verified IFC-to-FDS Framework.

Supports batch conversion, spatial scoping, inventory inspection, and
independent validation report generation.
"""

import argparse
import os
import sys
from typing import List, Optional

from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.geometry.engine import process_model_geometry
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.scope import SpatialScope, apply_spatial_scope
from ifc_to_fds.mep.mep_graph import extract_mep_graph
from ifc_to_fds.validation.acceptance import AcceptanceStatus
from ifc_to_fds.validation.engine import run_independent_validation


def cmd_inventory(args: argparse.Namespace) -> int:
    model, _ = extract_inventory(args.input_ifc)
    if args.json:
        print(model.model_dump_json(indent=2))
        return 0

    print(f"IFC Source: {model.source.filename} ({model.source.schema_version})")
    print(f"SHA-256: {model.source.file_hash_sha256}")
    print(f"Total Elements: {len(model.elements)}")
    print(f"Storeys ({len(model.storeys)}): {', '.join(model.storeys)}")
    counts = {}
    for el in model.elements:
        counts[el.ifc_type] = counts.get(el.ifc_type, 0) + 1
    print("\nElement Breakdown:")
    for t, c in sorted(counts.items()):
        print(f"  {t:30s}: {c:4d}")
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    print(f"[1/5] Ingesting IFC source: {args.input_ifc} ...")
    model, ifc_file = extract_inventory(args.input_ifc)

    print("[2/5] Building MEP and fire safety systems graph ...")
    model = extract_mep_graph(model, ifc_file)

    if args.storey:
        print(f"      Applying storey filter: {args.storey} ...")
        scope = SpatialScope(storeys=[args.storey])
        model = apply_spatial_scope(model, scope)

    print("[3/5] Computing watertight geometry with boolean subtractions ...")
    model = process_model_geometry(model, ifc_file)

    print(f"[4/5] Serializing FDS 6+ input namelist (cell_size={args.cell_size}m) ...")
    fds_text, manifest = serialize_fds(
        model,
        cell_size=args.cell_size,
        force_all_geom=args.all_geom,
        include_review_solids=args.include_review,
    )

    out_fds = args.output
    if not out_fds:
        base = os.path.splitext(args.input_ifc)[0]
        out_fds = f"{base}_verified.fds"

    out_dir = os.path.dirname(out_fds)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_fds, "w", encoding="utf-8") as f:
        f.write(fds_text)

    # Save manifest sidecars
    base_out = os.path.splitext(out_fds)[0]
    manifest_json_path = f"{base_out}_manifest.json"
    manifest_csv_path = f"{base_out}_manifest.csv"

    with open(manifest_json_path, "w", encoding="utf-8") as f:
        f.write(manifest.to_json())
    with open(manifest_csv_path, "w", encoding="utf-8") as f:
        f.write(manifest.to_csv())

    print(f"[5/5] Running independent 3-tier validation audit ...")
    report = run_independent_validation(model, fds_text)
    report_md_path = f"{base_out}_acceptance_report.md"
    report_json_path = f"{base_out}_acceptance_report.json"

    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())
    with open(report_json_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))

    print("\n" + "=" * 60)
    print(f"CONVERSION RESULT: {report.status.value}")
    print(f"  Emitted FDS File : {out_fds}")
    print(f"  Mapping Manifest : {manifest_json_path}")
    print(f"  Audit Report     : {report_md_path}")
    print(f"  Accounted Solids : {report.matched_count}/{report.total_elements_checked}")
    print(f"  Defect Summary   : P0={report.summary.get('P0', 0)}, P1={report.summary.get('P1', 0)}, P2={report.summary.get('P2', 0)}")
    print("=" * 60)

    if report.status == AcceptanceStatus.REJECTED:
        print("\n[WARNING] Output failed acceptance criteria. Review findings before simulation.")
        return 1
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn
    from ifc_to_fds.server import app

    print(f"Starting Verified IFCtoFDS server at http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ifc_to_fds",
        description="Verified IFC-to-FDS Geometry Mapping and Validation Framework",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: convert
    p_convert = subparsers.add_parser("convert", help="Convert IFC to verified FDS model with audit")
    p_convert.add_argument("input_ifc", help="Path to source .ifc file")
    p_convert.add_argument("-o", "--output", help="Path for generated .fds file")
    p_convert.add_argument("--cell-size", type=float, default=0.2, help="FDS mesh cell size in meters (default: 0.2)")
    p_convert.add_argument("--all-geom", action="store_true", help="Force all solid geometry to GEOM namelists")
    p_convert.add_argument("--include-review", action="store_true", help="Include furnishing, proxies, and MEP elements as obstacles")
    p_convert.add_argument("--storey", help="Filter export to a specific building storey name")
    p_convert.set_defaults(func=cmd_convert)

    # Subcommand: inventory
    p_inv = subparsers.add_parser("inventory", help="Inspect complete element inventory of an IFC file")
    p_inv.add_argument("input_ifc", help="Path to source .ifc file")
    p_inv.add_argument("--json", action="store_true", help="Output full JSON dump of canonical model")
    p_inv.set_defaults(func=cmd_inventory)

    # Subcommand: serve
    p_serve = subparsers.add_parser("serve", help="Run local REST API server and web workbench")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
