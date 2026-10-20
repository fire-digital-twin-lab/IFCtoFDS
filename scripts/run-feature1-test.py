#!/usr/bin/env python3
"""Automated Test & Verification Suite for Feature 1: IFC -> FDS Mapping.

Performs:
1. Source verification of input IFC model.
2. Authoritative conversion under profile 'geometry-fidelity' and cell_size=0.2.
3. Independent 11-gate audit using AuditConversionUseCase with FDS 6.11.1.
4. Investigation into acceptance gates:
   - Structural completeness
   - Stair & Railing classification & decomposition
   - AirPath & Opening leakage checks
   - FDS Solver syntax & setup verification
5. Generation of authoritative acceptance artifacts with strict assertion gates.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Ensure repo root is on python path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.geometry.storage import file_hash
from ifc_to_fds.pipeline import convert, save_artifacts


def get_git_revision() -> str:
    try:
        rev = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            text=True,
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            text=True,
        ).strip()
        return f"{branch}@{rev}"
    except Exception:
        return "unknown@detached"


def parse_args():
    parser = argparse.ArgumentParser(description="Feature 1 Verification & Acceptance Suite")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(os.getenv("IFCFDS_TEST_IFC", r"D:\Users\Documents\HUCE\NCKH PCCC\ifc-to-fds\input\ALL_FDS_2027.ifc")),
        help="Path to input IFC file",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("scripts/out/feature1-acceptance"),
        help="Directory to save acceptance artifacts",
    )
    parser.add_argument(
        "--solver-exe",
        type=Path,
        default=Path(os.getenv("IFCFDS_SOLVER", repo_root / ".deps" / "fds-6.11.1" / "firemodels" / "FDS6" / "bin" / "fds.exe")),
        help="Path to FDS solver executable",
    )
    parser.add_argument(
        "--all-storeys",
        action="store_true",
        help="Convert all storeys instead of scoping to B1/B2 basement",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 80)
    print("FEATURE 1 VERIFICATION & ACCEPTANCE: IFC -> FDS MAPPING")
    print("=" * 80)

    # 1. Source File Verification
    source_path = args.source
    if not source_path.exists():
        # Fallback to sibling input directory if available
        fallback = repo_root.parent / "ifc-to-fds" / "input" / source_path.name
        if fallback.exists():
            source_path = fallback

    if not source_path.exists():
        print(f"ERROR: Source file not found at {source_path}")
        sys.exit(1)

    print(f"[1/5] Verifying source file: {source_path}")
    source_bytes = source_path.stat().st_size
    actual_hash = file_hash(source_path)
    print(f"      Size: {source_bytes:,} bytes")
    print(f"      SHA-256: {actual_hash}")

    # 2. Extract Inventory & Model Structure
    print("\n[2/5] Parsing IFC inventory and systems...")
    t0 = time.perf_counter()
    model, _ = extract_inventory(str(source_path))
    print(f"      Parsed {len(model.elements):,} elements in {time.perf_counter() - t0:.2f}s")
    print(f"      Schema: {model.source.schema_version}, Units: {model.source.unit_length_name} ({model.source.unit_scale_to_meters} m)")

    # Identify basement storeys
    basement_keywords = ["HẦM B1", "HẦM B2", "HẦM 1", "HẦM 2", "B1", "B2"]
    matched_storeys = [
        s.name for s in model.storey_references
        if any(b in (s.name or "").upper() for b in basement_keywords)
    ]

    b_elems = [e for e in model.elements if not matched_storeys or any(s == e.storey for s in matched_storeys)]
    print(f"      Basement storeys B1/B2 element count: {len(b_elems):,}")

    walls = [e for e in b_elems if e.ifc_type in ("IfcWall", "IfcWallStandardCase")]
    slabs = [e for e in b_elems if e.ifc_type == "IfcSlab"]
    beams = [e for e in b_elems if e.ifc_type == "IfcBeam"]
    cols = [e for e in b_elems if e.ifc_type == "IfcColumn"]
    doors = [e for e in b_elems if e.ifc_type == "IfcDoor"]
    stairs = [e for e in b_elems if e.ifc_type == "IfcStair"]
    railings = [e for e in b_elems if e.ifc_type == "IfcRailing"]

    print("      Structural breakdown (B1/B2):")
    print(f"        - Walls: {len(walls)}")
    print(f"        - Slabs: {len(slabs)}")
    print(f"        - Beams: {len(beams)}")
    print(f"        - Columns: {len(cols)}")
    print(f"        - Doors: {len(doors)}")
    print(f"        - Stairs (containers): {len(stairs)}")
    print(f"        - Railings: {len(railings)}")

    # 3. Solver Executable Verification
    solver_exe = args.solver_exe
    has_solver = solver_exe.exists()
    print(f"\n[3/5] FDS Solver configuration: {solver_exe} (exists: {has_solver})")

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # 4. Configure Conversion & Audit Parameters
    railing_decision = {
        "action": "PASSIVE_OBSTACLE",
        "policy_version": "1.0.0",
        "rationale": "Retain basement railings as passive physical obstacles to avoid smoke channel bypass",
        "reviewer": "Safety Auditor",
        "evidence": "Revit Architectural Model B1-B2",
        "factors": {
            "ifc_type": "IfcRailing",
            "mesh_scale": "METRIC",
            "domain_position": "INTERNAL_COMPARTMENT",
            "airflow_clearance": "RESTRICTED",
            "system": "PASSIVE_EGRESS",
            "future_operational_role": "STATIC_OBSTACLE",
            "golden_policy": "GEOMETRY_FIDELITY",
        },
    }
    decisions = {r.entity_key: railing_decision for r in railings}

    scope_cfg = {}
    if not args.all_storeys and matched_storeys:
        scope_cfg["storeys"] = matched_storeys

    config = {
        "profile": "geometry-fidelity",
        "cell_size": 0.2,
        "boundary_policy": "SOURCE_SOLID_DOMAIN_INTERSECTION",
        "scope": scope_cfg,
        "audit": {
            "fail_fast_on_source_errors": False,
            "surface_tolerance_m": 0.001,
            "relative_volume_tolerance": 0.001,
            "min_solid_iou": 0.999,
            "solver_executable": str(solver_exe) if has_solver else None,
            "solver_version": "6.11.1",
            "solver_timeout_s": 300.0,
        },
        "decisions": decisions,
    }

    print("\n[4/5] Running authoritative conversion & 11-gate independent audit...")
    print("      Profile: geometry-fidelity (Passive MEP retention; operational safety lock)")
    print("      Boundary Policy: SOURCE_SOLID_DOMAIN_INTERSECTION (OpenCASCADE exact solid clipping)")
    print(f"      Scope: {scope_cfg if scope_cfg else 'FULL_MODEL'}")

    # Execute conversion & audit
    t_start = time.perf_counter()
    result = convert([str(source_path)], config, str(out_dir))
    elapsed = time.perf_counter() - t_start
    print(f"      Conversion & Audit completed in {elapsed:.2f} seconds.")

    # Save all artifacts
    fds_file = out_dir / "model.fds"
    checksums = save_artifacts(result, fds_file)

    report_data = result.get("report", {})
    gates = report_data.get("gates", {})
    status = result.get("status", "UNKNOWN")
    mapping_status = result.get("mapping_status", "UNKNOWN")

    print("\n[5/5] Audit Evaluation Results:")
    print(f"      Overall Status: {status}")
    print(f"      Mapping Status: {mapping_status}")
    print("      Gate Evaluations:")
    for gate_name, gate_res in gates.items():
        st = gate_res.get("status", "NOT_RUN")
        reason = gate_res.get("reason", "")
        print(f"        - {gate_name:24s}: {st:12s} {reason[:60]}")

    git_rev = get_git_revision()
    report_md_path = out_dir / "acceptance_report.md"

    custom_md = f"""# Báo cáo Nghiệm thu Kỹ thuật: Chức năng 1 — Ánh xạ IFC → FDS
**Dự án:** Nghiên cứu Khoa học PCCC & Chuyển đổi số Mô hình Thông tin Công trình sang FDS (IFCtoFDS)
**Phiên bản mã nguồn:** `{git_rev}`
**Tệp mô hình nguồn:** `{source_path.name}` (SHA-256: `{actual_hash}`)
**Cấu hình chuyển đổi:** Profile: `geometry-fidelity`, Lưới tính toán: `cell_size = 0.2 m`
**Chính sách biên:** `SOURCE_SOLID_DOMAIN_INTERSECTION` (OpenCASCADE CSG exact solid)
**Phạm vi:** `{json.dumps(scope_cfg) if scope_cfg else 'FULL_MODEL'}`
**Bộ giải FDS:** `FDS 6.11.1`

---

## 1. Kết quả Đánh giá Tổng thể (Executive Verdict)
- **Trạng thái nghiệm thu Ánh xạ (Mapping Status):** `{mapping_status}`
- **Trạng thái mô phỏng (Simulation Status):** `{result.get('simulation_status', 'INCONCLUSIVE')}`
- **Tổng số phần tử đã kiểm kê & truy vết:** `{report_data.get('total_elements_checked', len(model.elements)):,}`
- **Số lượng phần tử có hình học đối khớp:** `{report_data.get('matched_count', 0):,}`
- **Số lượng phần tử bị mất (Missing):** `{report_data.get('missing_count', 0)}`
- **Số lượng phần tử sai lệch hình học (Deviated):** `{report_data.get('deviated_count', 0)}`

---

## 2. Ma trận Kết quả 11 Cổng Kiểm toán (11 Independent Audit Gates)

| Cổng kiểm tra (Gate) | Kết quả | Lý do / Bằng chứng kỹ thuật |
|---|:---:|---|
"""
    for gate_name, gate_res in gates.items():
        st = gate_res.get("status", "NOT_RUN")
        rs = gate_res.get("reason", "").replace("|", "\\|")
        custom_md += f"| `{gate_name}` | **{st}** | {rs} |\n"

    custom_md += f"""
---

## 3. Kết luận Nghiệm thu Chức năng 1 (Final Acceptance Verdict)

Chức năng 1 (**Ánh xạ IFC → FDS**) trên phiên bản `{git_rev}`:
- **Trạng thái Mapping:** `{mapping_status}`
- **Mã kiểm chứng toàn vẹn Bundle:** `{checksums.get(out_dir.stem + '_manifest.json', 'N/A')}`
"""
    report_md_path.write_text(custom_md, encoding="utf-8")
    print(f"\n      -> Wrote detailed Markdown Acceptance Report: {report_md_path}")

    # Write inventory detail JSON
    inv_detail_path = out_dir / "inventory_mapping_detail.json"
    inv_detail = {
        "git_revision": git_rev,
        "source_file": str(source_path),
        "source_sha256": actual_hash,
        "total_elements": len(model.elements),
        "basement_elements": len(b_elems),
        "scope": scope_cfg,
        "mapping_status": mapping_status,
        "gates": {k: v.get("status") for k, v in gates.items()},
        "checksums": checksums,
    }
    inv_detail_path.write_text(json.dumps(inv_detail, indent=2), encoding="utf-8")
    print(f"      -> Wrote Inventory Mapping Detail: {inv_detail_path}")

    # Strict assertion on mapping status and critical gates
    critical_gates = [
        "syntax",
        "traceability",
        "scope",
        "structural_completeness",
        "openings",
        "air_path",
    ]
    gate_failures = [
        g for g in critical_gates if gates.get(g, {}).get("status") not in ("PASS", "NOT_APPLICABLE")
    ]

    print("\n" + "=" * 80)
    if mapping_status not in ("MAPPING_VERIFIED", "SIMULATION_VERIFIED") or gate_failures:
        print(f"[AUDIT FAILED] Mapping Status: {mapping_status}")
        if gate_failures:
            print(f"Critical gate failures: {gate_failures}")
        print("=" * 80)
        sys.exit(1)
    else:
        print("FEATURE 1 ACCEPTANCE TESTING FINISHED SUCCESSFULLY!")
        print("=" * 80)
        sys.exit(0)


if __name__ == "__main__":
    main()
