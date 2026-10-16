"""Local conversion, independent audit and inspection."""

import argparse
import json
from pathlib import Path
import sys
from .pipeline import convert, audit, save_artifacts
from .core.inventory import extract_inventory
from .mapping.manifest import MappingManifest


def exit_status(status):
    return {"VERIFIED": 0, "REJECTED": 1, "INCONCLUSIVE": 2}[str(status)]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ifc_to_fds")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("convert")
    p.add_argument("input_ifc", nargs="+")
    p.add_argument("-o", "--output")
    p.add_argument(
        "--config",
        help="JSON configuration with source transforms, scope and audit settings",
    )
    p.add_argument("--cell-size", type=float, default=None)
    p.add_argument("--storey", action="append")
    p.add_argument(
        "--bbox",
        nargs=6,
        type=float,
        metavar=("XMIN", "XMAX", "YMIN", "YMAX", "ZMIN", "ZMAX"),
    )
    p.add_argument("--all-geom", action="store_true", default=None)
    p.add_argument("--include-review", action="store_true", default=None)
    p.add_argument("--common-coordinates", action="store_true")
    p.add_argument("--solver")
    p = commands.add_parser("audit")
    p.add_argument("input_ifc", nargs="+")
    p.add_argument("--fds", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--config")
    p.add_argument("-o", "--output", required=True, help="Audit report JSON")
    p = commands.add_parser("inventory")
    p.add_argument("input_ifc")
    p.add_argument("--json", action="store_true")
    p = commands.add_parser("serve")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            import uvicorn

            uvicorn.run("ifc_to_fds.server:app", host=args.host, port=args.port)
            return 0
        if args.command == "inventory":
            model, _ = extract_inventory(args.input_ifc)
            print(
                model.model_dump_json(indent=2)
                if args.json
                else f"{model.source.filename}: {len(model.elements)} IfcProduct entities"
            )
            return 0
        config = (
            json.loads(Path(args.config).read_text(encoding="utf-8"))
            if args.config
            else {}
        )
        if args.command == "audit":
            manifest = MappingManifest.model_validate_json(
                Path(args.manifest).read_text(encoding="utf-8")
            )
            _, final, report = audit(
                args.input_ifc,
                Path(args.fds).read_text(encoding="utf-8"),
                manifest,
                config if args.config else None,
            )
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
            output.with_suffix(".md").write_text(report.to_markdown(), encoding="utf-8")
            print(report.status.value)
            return exit_status(report.status.value)
        for key in ("cell_size", "all_geom", "include_review"):
            if getattr(args, key) is not None:
                config[key] = getattr(args, key)
        if args.storey:
            config.setdefault("scope", {})["storeys"] = args.storey
        if args.bbox:
            config.setdefault("scope", {})["bounding_box"] = dict(
                zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), args.bbox)
            )
        if args.common_coordinates:
            config.setdefault("sources", {})["common_coordinates"] = True
        if args.solver:
            config.setdefault("audit", {})["solver_executable"] = args.solver
        result = convert(args.input_ifc, config)
        output = (
            args.output
            or str(Path(args.input_ifc[0]).with_suffix("")) + "_converted.fds"
        )
        save_artifacts(result, output)
        print(f"{result['status']}: {output}")
        return exit_status(result["status"])
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Conversion/audit error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
