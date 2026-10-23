"""Prepare a real import/re-export checklist; never infer GUI success from files.

python -m scripts.prepare_pyrosim_acceptance model.fds --output OUTPUT
Optional: --roundtrip reexport.fds --aliases aliases.json
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import copy

from ifc_to_fds.domain.validation import AuditConfig
from ifc_to_fds.modules.fds.api import MappingManifest, parse_fds
from ifc_to_fds.modules.verification.api import (
    compare_roundtrip_geometry,
    prepare_geometry_run,
    solver_gates,
    validate_editor_evidence,
    summarize_handoff,
    verification_capabilities,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--roundtrip", type=Path)
    parser.add_argument(
        "--import-evidence",
        type=Path,
        help="Human-reviewed session JSON with hashes of source/re-export/PSM/diagnostics",
    )
    parser.add_argument("--aliases", type=Path)
    parser.add_argument(
        "--ifc",
        type=Path,
        action="append",
        help="Reopen these original IFC files for independent mapping audit",
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--geometry-package", type=Path)
    parser.add_argument(
        "--solver",
        help="Pinned FDS executable; runs setup and a separate cold-flow companion",
    )
    parser.add_argument("--solver-version", default="6.11.1")
    parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="Cold-flow check duration in seconds; no fire scenario",
    )
    parser.add_argument(
        "--pyrosim-executable",
        type=Path,
        help="Explicit local installation; availability does not prove import",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit 2 until mapping, editor handoff and effective geometry are verified",
    )
    parser.add_argument(
        "--audit-config", type=Path,
        help="Approved AuditConfig JSON fields overriding the manifest audit settings",
    )
    args = parser.parse_args(argv)
    if any((args.ifc, args.manifest, args.geometry_package)) and not all(
        (args.ifc, args.manifest, args.geometry_package)
    ):
        parser.error(
            "--ifc, --manifest and --geometry-package must be supplied together"
        )
    if args.import_evidence and not args.roundtrip:
        parser.error("--import-evidence requires --roundtrip")
    source_bytes = args.source.read_bytes()
    text = source_bytes.decode("utf-8")
    exported_bytes = args.roundtrip.read_bytes() if args.roundtrip else None
    parsed = parse_fds(text)
    target = args.output / args.source.name
    protected = {
        p.resolve()
        for p in [
            args.source,
            args.roundtrip,
            args.manifest,
            args.geometry_package,
            args.aliases,
            args.import_evidence,
            args.audit_config,
            *(args.ifc or []),
        ]
        if p is not None
    }
    if args.import_evidence:
        try:
            reviewed = json.loads(args.import_evidence.read_text(encoding="utf-8"))
            for key in ("project", "diagnostics"):
                reference = reviewed.get(key, {}).get("file")
                if isinstance(reference, str) and reference:
                    protected.add((args.import_evidence.parent / reference).resolve())
        except (ValueError, AttributeError):
            pass  # The evidence validator will report malformed review data.
    outputs = [
        args.output / name
        for name in (
            "acceptance.json",
            "README.md",
            "mapping_audit.json",
            "audit_geometry.json",
            args.source.stem + "_cold.fds",
        )
    ]
    if args.source.resolve() != target.resolve():
        outputs.append(target)
    if any(path.resolve() in protected for path in outputs):
        raise ValueError(
            "Output would overwrite a supplied source or evidence file; choose a separate output directory"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    if args.source.resolve() != target.resolve():
        target.write_bytes(source_bytes)
    executable = (
        str(args.pyrosim_executable.resolve())
        if args.pyrosim_executable and args.pyrosim_executable.is_file()
        else shutil.which("pyrosim") or shutil.which("pyrosim.exe")
    )
    manifest = (
        MappingManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
        if args.manifest else None
    )
    # Resolve approval once. A partial explicit file overrides only its named
    # fields; it must not reset the manifest's other approved tolerances.
    approved = copy.deepcopy(manifest.configuration.get("audit", {}) if manifest else {})
    if args.audit_config:
        approved.update(json.loads(args.audit_config.read_text(encoding="utf-8")))
    config = AuditConfig.model_validate(approved)
    report = {
        "source": args.source.name,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "capabilities": verification_capabilities(),
        "audit_configuration": {
            "resolved": config.model_dump(mode="json"),
            "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest() if args.manifest else None,
            "override_sha256": hashlib.sha256(args.audit_config.read_bytes()).hexdigest() if args.audit_config else None,
        },
        "effective_geometry": {
            "status": "NOT_RUN",
            "reason": "Solver effective geometry not checked",
        },
        "roundtrip_effective_geometry": {
            "status": "NOT_RUN",
            "reason": "Re-export solver effective geometry not checked",
        },
        "pyrosim_import": {
            "status": "NOT_RUN" if executable else "BLOCKED",
            "reason": (
                "Interactive import evidence required"
                if executable
                else "PYROSIM_EXECUTABLE_UNAVAILABLE"
            ),
            "executable": executable,
        },
        "static_parse": {"errors": parsed.errors, "unsupported": parsed.unsupported},
        "syntax": {
            "status": (
                "FAIL"
                if parsed.errors
                else "INCONCLUSIVE" if parsed.unsupported else "PASS"
            ),
            "scope": "SUPPORTED_STATIC_FDS_SUBSET",
        },
        "mapping": {
            "status": "NOT_RUN",
            "reason": "Original IFC, manifest and geometry package not supplied",
        },
        "cold_flow": {"status": "NOT_RUN", "reason": "Pinned solver not supplied"},
        "roundtrip_solver": {
            "status": "NOT_RUN",
            "reason": "Re-export and pinned solver are required",
        },
        "expected_primitives": [
            {"id": r.id, "kind": r.kind, "source": r.source} for r in parsed.primitives
        ],
        "roundtrip_geometry": {
            "status": "NOT_RUN",
            "reason": "No PyroSim re-export supplied",
        },
    }
    if args.ifc:
        from ifc_to_fds.pipeline import audit
        from ifc_to_fds.modules.geometry.api import read_package, restore_package

        package = (
            restore_package(args.geometry_package, args.output / "audit_geometry.json")
            if args.geometry_package.suffix.lower() == ".zip"
            else read_package(args.geometry_package)
        )
        configuration = copy.deepcopy(manifest.configuration)
        configuration["audit"] = config.model_dump()
        if args.solver:
            configuration["audit"].update(
                solver_executable=args.solver,
                solver_version=args.solver_version,
                solver_evidence_directory=str(args.output / "setup-solver"),
            )
        _, _, audited = audit(args.ifc, text, manifest, configuration, package)
        (args.output / "mapping_audit.json").write_text(
            audited.model_dump_json(indent=2), encoding="utf-8"
        )
        report["mapping"] = {
            "status": (
                "PASS"
                if audited.mapping_status == "MAPPING_VERIFIED"
                else "FAIL" if audited.mapping_status == "REJECTED" else "INCONCLUSIVE"
            ),
            "mapping_status": audited.mapping_status.value,
            "source_sha256": {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.ifc
            },
            "fds_sha256": report["source_sha256"],
            "report": "mapping_audit.json",
        }
        report["setup_solver"] = audited.gates["solver"].model_dump(mode="json")
        report["effective_geometry"] = audited.gates["effective_geometry"].model_dump(
            mode="json"
        )
    if args.solver and report["mapping"]["status"] != "FAIL":
        run_config = config.model_copy(
            update={
                "solver_executable": args.solver,
                "solver_version": args.solver_version,
                "solver_evidence_directory": str(args.output / "cold-solver"),
            }
        )
        if "setup_solver" not in report:
            setup, effective = solver_gates(text, run_config)
            report["setup_solver"] = setup.model_dump(mode="json")
            report["effective_geometry"] = effective.model_dump(mode="json")
        try:
            cold, derivation = prepare_geometry_run(text, args.duration)
            cold_path = args.output / (args.source.stem + "_cold.fds")
            if cold_path.resolve() == args.source.resolve():
                raise ValueError("Cold-flow output must not overwrite the original")
            cold_path.write_bytes(cold.encode("utf-8"))
            gate, effective = solver_gates(cold, run_config)
            report["cold_flow"] = gate.model_dump(mode="json")
            report["effective_geometry"] = effective.model_dump(mode="json")
            report["cold_flow"].update(
                derivation=derivation,
                file=cold_path.name,
                effective_geometry=effective.model_dump(mode="json"),
            )
        except ValueError as exc:
            report["cold_flow"] = {"status": "INCONCLUSIVE", "reason": str(exc)}
    if args.roundtrip:
        aliases = (
            json.loads(args.aliases.read_text(encoding="utf-8")) if args.aliases else {}
        )
        report["roundtrip_geometry"] = compare_roundtrip_geometry(
            text, exported_bytes.decode("utf-8"), config, aliases
        ).model_dump(mode="json")
        if args.solver and report["roundtrip_geometry"]["status"] == "PASS":
            exported = exported_bytes.decode("utf-8")
            exported_config = config.model_copy(
                update={
                    "solver_executable": args.solver,
                    "solver_version": args.solver_version,
                    "solver_evidence_directory": str(args.output / "reexport-solver"),
                }
            )
            setup, effective = solver_gates(exported, exported_config)
            report["roundtrip_effective_geometry"] = effective.model_dump(mode="json")
            report["roundtrip_solver"] = setup.model_dump(mode="json")
            if (
                setup.status == "PASS"
                and setup.evidence.get("completion", {}).get("mode") == "SETUP_ONLY"
            ):
                try:
                    cold, derivation = prepare_geometry_run(exported, args.duration)
                    gate, effective = solver_gates(cold, exported_config)
                    report["roundtrip_effective_geometry"] = effective.model_dump(
                        mode="json"
                    )
                    report["roundtrip_solver"] = gate.model_dump(mode="json")
                    report["roundtrip_solver"].update(
                        derivation=derivation, setup=setup.model_dump(mode="json")
                    )
                except ValueError as exc:
                    report["roundtrip_solver"] = {
                        "status": "INCONCLUSIVE",
                        "reason": str(exc),
                    }
    if args.import_evidence:
        try:
            document = json.loads(args.import_evidence.read_text(encoding="utf-8"))
            artifacts = {}
            for key in ("project", "diagnostics"):
                relative = document.get(key, {}).get("file")
                if isinstance(relative, str) and relative:
                    artifacts[key] = (
                        args.import_evidence.parent / relative
                    ).read_bytes()
            report["pyrosim_import"] = validate_editor_evidence(
                document,
                source_bytes,
                exported_bytes,
                artifacts,
            ).model_dump(mode="json")
        except (OSError, ValueError, AttributeError) as exc:
            report["pyrosim_import"] = {
                "status": "FAIL",
                "reason": f"Invalid import evidence: {exc}",
            }
    report["handoff"], report["verification"] = summarize_handoff(report)
    failed = bool(parsed.errors) or report["verification"]["status"] == "FAIL"
    if parsed.errors:
        report["handoff"]["status"] = report["verification"]["status"] = "FAIL"
    (args.output / "acceptance.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    template = args.output / "import-evidence.template.json"
    if not template.exists():
        document = {
            "pyrosim_version": "", "reviewer": "", "imported_at": "",
            "import_result": "PENDING", "warnings_review": "",
            "source_sha256": report["source_sha256"], "exported_sha256": "",
            "project": {"file": "model.psm", "sha256": ""},
            "diagnostics": {"file": "import-diagnostics.txt", "sha256": ""},
        }
        with template.open("x", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2)
    (args.output / "README.md").write_text(
        "# Nghiệm thu nhập FDS vào PyroSim\n\n"
        "acceptance.json ghi trạng thái theo bằng chứng hiện có. Chuẩn bị gói này chưa chạy PyroSim.\n\n"
        "1. Ghi phiên bản PyroSim và tình trạng giấy phép/môi trường chạy.\n"
        "2. Chọn File > Import FDS/CAD File, chọn FDS trong gói và định dạng FDS6.\n"
        "3. Lưu toàn bộ thông báo nhập, gồm cảnh báo về record không hỗ trợ hoặc bị bỏ.\n"
        "4. Kiểm tra solid, khoảng rỗng ống gió, lỗ mở, đơn vị và tọa độ; lưu dự án .psm.\n"
        "   Với GEOM, bật hỗ trợ FDS GEOM và giữ biểu diễn immersed khi xuất lại; kiểm tra cài đặt theo phiên bản PyroSim.\n"
        "5. Xuất FDS ra file mới; chạy lại lệnh với --roundtrip. Dung sai lấy từ manifest; chỉ dùng --audit-config để ghi đè các trường đã được phê duyệt.\n"
        "6. Nếu ID thay đổi, cung cấp --aliases; alias vẫn phải được chứng minh tương đương hình học.\n"
        "7. Giữ FDS gốc, thông báo nhập, PSM, FDS xuất lại và acceptance.json cùng nhau.\n\n"
        "8. File *_cold.fds (nếu có) chỉ đổi T_END để kiểm tra solver tiến thời gian; không đổi hình học/miền và không thêm cháy hay vận hành MEP.\n"
        "9. Chạy solver đi kèm PyroSim trên file xuất lại và lưu log; đối chiếu phiên bản với solver đã kiểm tra.\n"
        "10. Người review ghi import-evidence.json: pyrosim_version, reviewer, imported_at (ISO có múi giờ), import_result=IMPORTED, warnings_review; source_sha256/exported_sha256; project/diagnostics mỗi mục có file và sha256. Chạy lại với --import-evidence và --roundtrip. Đây là chứng nhận thủ công, không phải GUI tự động.\n\n"
        "Có thể sao chép import-evidence.template.json thành import-evidence.json để điền sau khi nhập thật. Template giữ PENDING và không phải bằng chứng đã nghiệm thu.\n\n"
        "--ifc + --manifest + --geometry-package chạy lại audit nguồn độc lập. --solver chạy thêm setup và cold-flow; --require-ready trả mã 2 khi còn thiếu bằng chứng.\n\n"
        "handoff kiểm tra bàn giao qua editor; verification yêu cầu thêm hình học hiệu dụng của cả bản gốc và bản xuất lại. GEOM cut-cells chưa được chứng minh thì verification không thể PASS, kể cả khi handoff đã PASS.\n\n"
        "PASS đối chiếu hình học tĩnh chưa chứng minh đã chạy GUI hoặc đúng vật lý mô phỏng.\n\n"
        "Hướng dẫn chính thức: https://www.thunderheadeng.com/docs/2026-1/pyrosim/fds-files/import/\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "pyrosim_import": report["pyrosim_import"],
                "roundtrip_geometry": report["roundtrip_geometry"]["status"],
                "mapping": report["mapping"]["status"],
                "cold_flow": report["cold_flow"]["status"],
                "handoff": report["handoff"]["status"],
                "verification": report["verification"]["status"],
            }
        )
    )
    return (
        1
        if failed
        else (
            2
            if args.require_ready and report["verification"]["status"] != "PASS"
            else 0
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
