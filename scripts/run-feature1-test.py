#!/usr/bin/env python3
"""Run technical IFC-to-FDS mapping verification and write evidence artifacts.

This mapping run is not B1/B2 research acceptance. Storey IDs and a separate
simulation domain must be supplied explicitly; this script does not verify the
domain's physical basis or approve a research reference.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

from pydantic import ValidationError

# Ensure repo root is on python path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.domain.bim import BoundingBox, CanonicalModel
from ifc_to_fds.geometry.storage import file_hash
from ifc_to_fds.pipeline import convert, save_artifacts
from ifc_to_fds.validation.golden import inspect_case


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
    parser = argparse.ArgumentParser(
        description="Feature 1 technical mapping verification; not research acceptance"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(
            os.getenv(
                "IFCFDS_TEST_IFC",
                r"D:\Users\Documents\HUCE\NCKH PCCC\ifc-to-fds\input\ALL_FDS_2027.ifc",
            )
        ),
        help="Path to input IFC file",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("scripts/out/feature1-technical-verification"),
        help="Directory to save technical verification artifacts",
    )
    parser.add_argument(
        "--solver-exe",
        type=Path,
        default=Path(
            os.getenv(
                "IFCFDS_SOLVER",
                repo_root / ".deps" / "fds-6.11.1" / "firemodels" / "FDS6" / "bin" / "fds.exe",
            )
        ),
        help="Path to FDS solver executable",
    )
    parser.add_argument(
        "--storey-id",
        action="append",
        required=True,
        help="Source-qualified IFC storey id; repeat once for B1 and once for B2",
    )
    parser.add_argument(
        "--storey-label",
        action="append",
        choices=("B1", "B2"),
        required=True,
        help="Assert each explicit storey id's label; repeat with matching ids",
    )
    parser.add_argument(
        "--reference-case",
        type=Path,
        default=repo_root / "reference-cases" / "basement-b1-b2",
        help="Reference case used to verify source identity and report its approval state",
    )
    parser.add_argument(
        "--simulation-domain",
        type=Path,
        required=True,
        help="JSON file declaring the independently reviewed FDS simulation domain",
    )
    parser.add_argument(
        "--domain-evidence",
        type=Path,
        required=True,
        help="Source or review document used to support a candidate simulation domain",
    )
    return parser.parse_args()


def verify_reference_case(
    reference_case: Path, actual_source_hash: str
) -> dict[str, object | dict[str, float] | None]:
    try:
        checksum, approval, bundle = inspect_case(reference_case)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError(f"Reference case failed integrity checks: {exc}") from exc
    if not isinstance(approval, dict) or not isinstance(bundle, dict):
        raise ValueError("Reference approval and bundle roots must be JSON objects")

    source_document = bundle.get("sources.json")
    if not isinstance(source_document, dict):
        raise ValueError("Reference sources.json must be a JSON object")
    entries = source_document.get("sources", [])
    if not isinstance(entries, list) or len(entries) != 1:
        raise ValueError("Feature 1 currently requires one source entry")
    if not isinstance(entries[0], dict):
        raise ValueError("Reference source entry must be a JSON object")
    expected_hash = entries[0].get("file_hash_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ValueError("Reference case has no valid source SHA-256")
    if expected_hash.lower() != actual_source_hash.lower():
        raise ValueError(
            f"Source SHA-256 does not match reference case: expected {expected_hash}, "
            f"got {actual_source_hash}"
        )

    status = approval.get("status", "UNKNOWN")
    if status not in ("DRAFT", "APPROVED"):
        raise ValueError(f"Reference case status is not eligible for verification: {status}")
    if approval.get("bundle_sha256") != checksum:
        raise ValueError("Reference approval digest does not match its current bundle")

    scope_document = bundle.get("scope.json")
    if not isinstance(scope_document, dict):
        raise ValueError("Reference scope.json must be a JSON object")
    approved_domain = None
    raw_domain = scope_document.get("simulation_domain")
    if status == "APPROVED" and raw_domain is None:
        raise ValueError("Approved reference case has no independently reviewed simulation domain")
    if raw_domain is not None:
        try:
            domain = BoundingBox.model_validate(raw_domain)
        except ValidationError as exc:
            raise ValueError("Reference simulation domain is invalid") from exc
        approved_domain = {
            "xmin": domain.xmin,
            "xmax": domain.xmax,
            "ymin": domain.ymin,
            "ymax": domain.ymax,
            "zmin": domain.zmin,
            "zmax": domain.zmax,
        }
    if status == "APPROVED":
        if not all(approval.get(key) for key in ("reviewer", "rationale", "evidence")):
            raise ValueError("Approved reference case lacks human approval evidence")
        if approved_domain is None:
            raise ValueError("Approved reference case has no independently reviewed simulation domain")

    raw_scope = scope_document.get("scope", {})
    scope_storeys = raw_scope.get("storeys", []) if isinstance(raw_scope, dict) else []
    if status == "APPROVED" and not isinstance(raw_scope, dict):
        raise ValueError("Approved B1/B2 reference scope is malformed")
    if status == "APPROVED" and (
        not isinstance(scope_storeys, list)
        or any(not isinstance(storey_id, str) for storey_id in scope_storeys)
        or len(scope_storeys) != 2
        or len(set(scope_storeys)) != 2
    ):
        raise ValueError("Approved B1/B2 reference must bind exactly two source-qualified storey IDs")
    return {
        **approval,
        "bundle_sha256": checksum,
        "source_sha256": expected_hash.lower(),
        "simulation_domain": approved_domain,
        "scope_storey_ids": scope_storeys if status == "APPROVED" else [],
        "reference_scope_status": "APPROVED" if status == "APPROVED" else "UNAPPROVED_DRAFT",
        "approved_reference": status == "APPROVED",
    }


def load_simulation_domain(
    path: Path, evidence_path: Path, approved_domain: dict[str, float] | None
) -> tuple[dict[str, float], dict[str, str]]:
    if not evidence_path.is_file():
        raise ValueError(f"Domain evidence file does not exist: {evidence_path}")
    if evidence_path.stat().st_size == 0:
        raise ValueError(f"Domain evidence file is empty: {evidence_path}")

    try:
        raw_domain = json.loads(path.read_text(encoding="utf-8"))
        domain = BoundingBox.model_validate(raw_domain)
        evidence_digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    except (OSError, json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise ValueError(f"Invalid simulation domain or evidence in {path}: {exc}") from exc

    domain_values = {
        "xmin": domain.xmin,
        "xmax": domain.xmax,
        "ymin": domain.ymin,
        "ymax": domain.ymax,
        "zmin": domain.zmin,
        "zmax": domain.zmax,
    }
    if approved_domain is not None and domain_values != approved_domain:
        raise ValueError("Provided simulation domain differs from the reference domain")
    if approved_domain is None:
        print("WARNING: supplied domain is a technical input, not an approved reference domain")
    return domain_values, {"file": str(evidence_path), "sha256": evidence_digest}


def verify_converted_source_hash(manifest: dict, expected_hash: str) -> None:
    sources = manifest.get("sources", [])
    if len(sources) != 1:
        raise ValueError("Feature 1 technical verification requires one converted source")
    converted_hash = sources[0].get("file_hash_sha256", sources[0].get("source_id"))
    if not isinstance(converted_hash, str) or converted_hash.lower() != expected_hash.lower():
        raise ValueError(
            "Converted source hash differs from the reference-verified IFC; "
            "discard this run and verify the source file was not replaced"
        )


def basement_label(storey_name: str) -> str | None:
    normalized = " ".join(unicodedata.normalize("NFKC", storey_name).upper().split())
    if normalized in ("HẦM B1", "HẦM 1", "B1"):
        return "B1"
    if normalized in ("HẦM B2", "HẦM 2", "B2"):
        return "B2"
    return None


def validate_storey_ids(
    model: CanonicalModel,
    storey_ids: list[str],
    storey_labels: list[str],
    reference_storey_ids: list[str] | None = None,
) -> list[str]:
    if len(storey_ids) != 2 or len(storey_labels) != 2:
        raise ValueError("Exactly two source-qualified --storey-id and two --storey-label values are required")
    if len(storey_ids) != len(set(storey_ids)):
        raise ValueError("Duplicate --storey-id values are not allowed")
    if sorted(storey_labels) != ["B1", "B2"]:
        raise ValueError("Storey labels must contain exactly one B1 and one B2")

    references = {storey.storey_id: storey for storey in model.storey_references}
    missing = [storey_id for storey_id in storey_ids if storey_id not in references]
    if missing:
        raise ValueError(
            "Unknown or non-source-qualified storey id(s): " + ", ".join(missing)
        )
    if any(references[storey_id].source_id != model.source.source_id for storey_id in storey_ids):
        raise ValueError("Selected storeys must belong to the verified source IFC")
    building_ids = {references[storey_id].building_id for storey_id in storey_ids}
    if len(building_ids) != 1 or None in building_ids:
        raise ValueError("Selected B1 and B2 storeys must belong to the same identified building")
    actual_labels = [basement_label(references[storey_id].name) for storey_id in storey_ids]
    if any(label is None for label in actual_labels) or set(actual_labels) != {"B1", "B2"}:
        raise ValueError("Selected storey IDs must resolve to exactly one B1 and one B2 label")
    expected = dict(zip(storey_ids, storey_labels))
    if any(actual_labels[index] != expected[storey_ids[index]] for index in range(2)):
        raise ValueError("Each --storey-label must match the exact source-qualified storey ID")
    if reference_storey_ids and set(storey_ids) != set(reference_storey_ids):
        raise ValueError(
            "Selected B1/B2 storeys differ from the reference case scope; "
            "use a new reviewed reference revision to change that selection"
        )
    return storey_ids


def main():
    args = parse_args()
    print("=" * 80)
    print("FEATURE 1 TECHNICAL MAPPING VERIFICATION: IFC -> FDS")
    print("=" * 80)

    source_path = args.source
    if not source_path.exists():
        fallback = repo_root.parent / "ifc-to-fds" / "input" / source_path.name
        if fallback.exists():
            source_path = fallback

    if not source_path.exists():
        print(f"ERROR: Source file not found at {source_path}")
        sys.exit(1)

    print(f"[1/5] Verifying source file: {source_path}")
    source_bytes = source_path.stat().st_size
    actual_hash = file_hash(source_path)
    try:
        reference_approval = verify_reference_case(args.reference_case, actual_hash)
        if reference_approval["approved_reference"] and not args.domain_evidence.is_file():
            raise ValueError("Approved reference status requires its evidence file to be available")
        reference_domain_value = reference_approval["simulation_domain"]
        if reference_domain_value is not None and not isinstance(reference_domain_value, dict):
            raise ValueError("Reference simulation domain has an invalid representation")
        approved_domain = (
            reference_domain_value
            if reference_approval["approved_reference"]
            else None
        )
        simulation_domain, domain_evidence = load_simulation_domain(
            args.simulation_domain,
            args.domain_evidence,
            approved_domain,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    print(f"      Size: {source_bytes:,} bytes")
    print(f"      SHA-256: {actual_hash}")
    print(f"      Reference case: {args.reference_case} ({reference_approval['status']})")

    print("\n[2/5] Parsing IFC inventory and systems...")
    t0 = time.perf_counter()
    model, _ = extract_inventory(str(source_path))
    parsed_source_hash = model.source.file_hash_sha256
    post_inventory_hash = file_hash(source_path)
    if (
        parsed_source_hash.lower() != actual_hash.lower()
        or post_inventory_hash.lower() != actual_hash.lower()
    ):
        raise ValueError("Source IFC changed during reference verification or inventory extraction")
    print(f"      Parsed {len(model.elements):,} elements in {time.perf_counter() - t0:.2f}s")
    print(
        f"      Schema: {model.source.schema_version}, Units: "
        f"{model.source.unit_length_name} ({model.source.unit_scale_to_meters} m)"
    )

    try:
        reference_storey_ids = reference_approval["scope_storey_ids"]
        if not isinstance(reference_storey_ids, list) or any(
            not isinstance(storey_id, str) for storey_id in reference_storey_ids
        ):
            raise ValueError("Reference case scope storey IDs are malformed")
        selected_storey_ids = validate_storey_ids(
            model,
            args.storey_id,
            args.storey_label,
            reference_storey_ids,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    selected_storeys = [
        storey for storey in model.storey_references if storey.storey_id in selected_storey_ids
    ]
    selected_elements = [
        element for element in model.elements if element.storey_id in selected_storey_ids
    ]
    selected_names = [storey.name for storey in selected_storeys]
    print(f"      Selected source-qualified storey ids: {selected_storey_ids}")
    print(f"      Selected storey labels (display only): {selected_names}")
    print(f"      Directly assigned selected-storey elements: {len(selected_elements):,}")

    walls = [e for e in selected_elements if e.ifc_type in ("IfcWall", "IfcWallStandardCase")]
    slabs = [e for e in selected_elements if e.ifc_type == "IfcSlab"]
    beams = [e for e in selected_elements if e.ifc_type == "IfcBeam"]
    cols = [e for e in selected_elements if e.ifc_type == "IfcColumn"]
    doors = [e for e in selected_elements if e.ifc_type == "IfcDoor"]
    stairs = [e for e in selected_elements if e.ifc_type == "IfcStair"]
    railings = [e for e in selected_elements if e.ifc_type == "IfcRailing"]

    print("      Structural breakdown for directly assigned selected storeys:")
    print(f"        - Walls: {len(walls)}")
    print(f"        - Slabs: {len(slabs)}")
    print(f"        - Beams: {len(beams)}")
    print(f"        - Columns: {len(cols)}")
    print(f"        - Doors: {len(doors)}")
    print(f"        - Stairs (containers): {len(stairs)}")
    print(f"        - Railings: {len(railings)}")

    solver_exe = args.solver_exe
    has_solver = solver_exe.exists()
    print(f"\n[3/5] FDS Solver configuration: {solver_exe} (exists: {has_solver})")

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    scope_cfg = {"storeys": selected_storey_ids}
    config = {
        "profile": "geometry-fidelity",
        "cell_size": 0.2,
        "boundary_policy": "SOURCE_SOLID_DOMAIN_INTERSECTION",
        "scope": scope_cfg,
        "simulation_domain": simulation_domain,
        "audit": {
            "fail_fast_on_source_errors": False,
            "surface_tolerance_m": 0.001,
            "relative_volume_tolerance": 0.001,
            "min_solid_iou": 0.999,
            "solver_executable": str(solver_exe) if has_solver else None,
            "solver_version": "6.11.1",
            "solver_timeout_s": 300.0,
        },
    }

    print("\n[4/5] Running technical conversion & independent audit...")
    print("      Profile: geometry-fidelity")
    print("      Boundary Policy: SOURCE_SOLID_DOMAIN_INTERSECTION")
    print(f"      Scope storey ids: {selected_storey_ids}")
    print(f"      Input simulation domain: {simulation_domain}")
    print(f"      Reference simulation domain: {reference_approval['simulation_domain']}")

    t_start = time.perf_counter()
    result = convert([str(source_path)], config, str(out_dir))
    elapsed = time.perf_counter() - t_start
    print(f"      Conversion & Audit completed in {elapsed:.2f} seconds.")

    manifest = result.get("manifest", {})
    verify_converted_source_hash(manifest, actual_hash)
    if reference_approval["approved_reference"]:
        reference_domain = reference_approval["simulation_domain"]
        if simulation_domain != reference_domain:
            raise ValueError("Approved reference domain does not match conversion configuration")

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
        gate_status = gate_res.get("status", "NOT_RUN")
        reason = gate_res.get("reason", "")
        print(f"        - {gate_name:24s}: {gate_status:12s} {reason[:60]}")

    git_rev = get_git_revision()
    solver_status = gates.get("solver", {}).get("status", "NOT_RUN")
    manifest_checksum = next(
        (
            value
            for filename, value in checksums.items()
            if filename.endswith("_manifest.json")
        ),
        "N/A",
    )
    report_md_path = out_dir / "acceptance_report.md"
    custom_md = f"""# Báo cáo kiểm chứng kỹ thuật: IFC → FDS
**Dự án:** IFCtoFDS
**Phiên bản mã nguồn:** `{git_rev}`
**Tệp mô hình nguồn:** `{source_path.name}` (SHA-256: `{actual_hash}`; rechecked after inventory)
**Cấu hình chuyển đổi:** Profile: `geometry-fidelity`, `cell_size = 0.2 m`
**Chính sách biên:** `SOURCE_SOLID_DOMAIN_INTERSECTION`
**Storey IDs:** `{json.dumps(selected_storey_ids)}`
**Simulation domain (input):** `{json.dumps(simulation_domain)}`
**Domain evidence input digest:** `{domain_evidence['sha256']}`
**Reference status:** `{reference_approval['status']}`
**Reference bundle digest:** `{reference_approval['bundle_sha256']}`
**Reference domain:** `{json.dumps(reference_approval['simulation_domain'])}`
**Manifest checksum:** `{manifest_checksum}`
**FDS 6.11.1 solver gate:** `{solver_status}`

> Đây là kết quả kiểm chứng kỹ thuật của lần chạy, không phải kết luận nghiệm thu nghiên cứu B1/B2.
> Reference status được ghi lại ở trên; script này không thực thi toàn bộ research acceptance protocol.

---

## 1. Kết quả đánh giá
- **Trạng thái tổng thể:** `{status}`
- **Trạng thái mapping:** `{mapping_status}`
- **Tổng số phần tử trong source:** `{report_data.get('total_elements_checked', len(model.elements)):,}`
- **Số lượng phần tử khớp hình học:** `{report_data.get('matched_count', 0):,}`
- **Số lượng phần tử thiếu:** `{report_data.get('missing_count', 0)}`
- **Số lượng phần tử sai lệch:** `{report_data.get('deviated_count', 0)}`

## 2. Kết quả cổng kiểm toán

| Gate | Kết quả | Lý do / bằng chứng |
|---|:---:|---|
"""
    for gate_name, gate_res in gates.items():
        gate_status = gate_res.get("status", "NOT_RUN")
        reason = gate_res.get("reason", "").replace("|", "\\|")
        custom_md += f"| `{gate_name}` | **{gate_status}** | {reason} |\n"

    custom_md += f"""

## 3. Kết luận

- **Mapping status:** `{mapping_status}`
- **Manifest checksum:** `{manifest_checksum}`
- **Reference approval:** `{reference_approval['status']}`
- **Research acceptance:** `NOT_ESTABLISHED`
- **Ghi chú:** runner này không kiểm tra toàn bộ research acceptance gates; không được hiểu technical mapping PASS là research PASS.
"""
    report_md_path.write_text(custom_md, encoding="utf-8")
    print(f"\n      -> Wrote technical verification report: {report_md_path}")

    inv_detail_path = out_dir / "inventory_mapping_detail.json"
    inv_detail = {
        "git_revision": git_rev,
        "source_file": str(source_path),
        "source_sha256": actual_hash,
        "total_elements": len(model.elements),
        "selected_storey_elements": len(selected_elements),
        "selected_storey_ids": selected_storey_ids,
        "input_simulation_domain": simulation_domain,
        "reference_simulation_domain": reference_approval["simulation_domain"],
        "domain_evidence": domain_evidence,
        "reference_case": str(args.reference_case),
        "reference_status": reference_approval["status"],
        "reference_bundle_sha256": reference_approval["bundle_sha256"],
        "solver_gate_status": solver_status,
        "scope": scope_cfg,
        "mapping_status": mapping_status,
        "research_acceptance": "NOT_ESTABLISHED",
        "gates": {key: value.get("status") for key, value in gates.items()},
        "checksums": checksums,
    }
    inv_detail_path.write_text(json.dumps(inv_detail, indent=2), encoding="utf-8")
    print(f"      -> Wrote inventory mapping detail: {inv_detail_path}")

    critical_gates = [
        "syntax",
        "traceability",
        "scope",
        "structural_completeness",
        "openings",
        "air_path",
    ]
    gate_failures = [
        gate
        for gate in critical_gates
        if gates.get(gate, {}).get("status") not in ("PASS", "NOT_APPLICABLE")
    ]

    print("\n" + "=" * 80)
    if mapping_status not in ("MAPPING_VERIFIED", "SIMULATION_VERIFIED") or gate_failures:
        print(f"[TECHNICAL VERIFICATION FAILED] Mapping Status: {mapping_status}")
        if gate_failures:
            print(f"Critical gate failures: {gate_failures}")
        print("Research acceptance remains NOT_ESTABLISHED.")
        print("=" * 80)
        sys.exit(1)

    print("TECHNICAL MAPPING VERIFICATION FINISHED SUCCESSFULLY!")
    print("Research acceptance remains NOT_ESTABLISHED.")
    print("=" * 80)
    sys.exit(0)


if __name__ == "__main__":
    main()
