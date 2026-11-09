"""Sinh sổ CVE từ Trivy JSON: mô tả bằng chứng, không phê duyệt ngoại lệ.

Mọi CVE mặc định UNREVIEWED; không gắn PASS cho release hoặc scientific V&V.
Chỉ các finding đúng trong scanner mới xuất hiện; thiếu nguồn phải fail-closed.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys


_SHA = re.compile(r"^[a-f0-9]{40}$")
_IMAGE = re.compile(r"^sha256:[a-f0-9]{64}$")
_CVE = re.compile(r"^CVE-\d{4}-\d{4,}$")
_SEVERITY = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


class TriageContractError(ValueError):
    """Thiếu/không hợp lệ chứng cứ đầu vào."""


def make_triage_report(
    scan_data: dict, *, source_sha: str, image_id: str, scan_sha256: str
) -> dict:
    if not _SHA.fullmatch(source_sha):
        raise TriageContractError("Invalid source SHA")
    if not _IMAGE.fullmatch(image_id):
        raise TriageContractError("Invalid container image ID")
    if not re.fullmatch(r"[a-f0-9]{64}", scan_sha256):
        raise TriageContractError("Invalid Trivy artifact SHA-256")
    if (
        not isinstance(scan_data, dict)
        or scan_data.get("SchemaVersion") != 2
        or scan_data.get("ArtifactName") != "ifctofds:security"
        or scan_data.get("ArtifactType") != "container_image"
    ):
        raise TriageContractError("Unexpected Trivy image report")
    meta = scan_data.get("Metadata")
    if not isinstance(meta, dict) or meta.get("ImageID") != image_id:
        raise TriageContractError("Trivy image identity cannot be verified")
    sections = scan_data.get("Results")
    if not isinstance(sections, list):
        raise TriageContractError("Missing scanner Results")

    groups: dict[str, list[dict]] = defaultdict(list)
    severity_count = {"HIGH": 0, "CRITICAL": 0}
    for section in sections:
        if not isinstance(section, dict):
            raise TriageContractError("Invalid Results item")
        target = section.get("Target")
        if not isinstance(target, str) or not target:
            raise TriageContractError("Trivy target must be nonempty")
        vulns = section.get("Vulnerabilities", [])
        if vulns is None:
            vulns = []
        if not isinstance(vulns, list):
            raise TriageContractError("Invalid vulnerability collection")
        for v in vulns:
            if not isinstance(v, dict):
                raise TriageContractError("Invalid vulnerability item")
            cve, severity = v.get("VulnerabilityID"), v.get("Severity")
            if not isinstance(cve, str) or not _CVE.fullmatch(cve):
                raise TriageContractError("Unsupported vulnerability ID; review scanner")
            if severity not in severity_count:
                raise TriageContractError("Expected scanner filtered to HIGH/CRITICAL")
            name, installed = v.get("PkgName"), v.get("InstalledVersion")
            if not isinstance(name, str) or not name or not isinstance(installed, str) or not installed:
                raise TriageContractError("Missing installed package provenance")
            fixed = v.get("FixedVersion")
            if fixed is not None and not isinstance(fixed, str):
                raise TriageContractError("Invalid fixed package version")
            severity_count[severity] += 1
            groups[cve].append({
                "package": name,
                "installed_version": installed,
                "fixed_version": fixed or None,
                "scanner_status": v.get("Status") or "UNSPECIFIED",
                "severity": severity,
                "target": target,
            })

    entries = []
    for cve in sorted(groups):
        packages = sorted(
            groups[cve],
            key=lambda x: (
                x["target"], x["package"], x["installed_version"]
            ),
        )
        candidates = sum(bool(x["fixed_version"]) for x in packages)
        if candidates == len(packages):
            patch = "ALL_FINDINGS_HAVE_FIXED_VERSION"
        elif candidates:
            patch = "PARTIAL_FIXED_VERSION"
        else:
            patch = "NO_FIXED_VERSION_IN_SCAN"
        entries.append({
            "cve_id": cve,
            "max_severity": max(
                (x["severity"] for x in packages), key=_SEVERITY.__getitem__
            ),
            "findings_count": len(packages),
            "patch_availability": patch,
            "triage_status": "UNREVIEWED",
            "decision_owner": None,
            "decision_evidence": None,
            "exception_expiry": None,
            "affected_packages": packages,
        })

    return {
        "schema": 1,
        "source_sha": source_sha,
        "local_image_id": image_id,
        "scan_sha256": scan_sha256,
        "scanner_created_at": scan_data.get("CreatedAt"),
        "os": meta.get("OS"),
        "finding_counts": severity_count,
        "unique_cve_count": len(entries),
        "patch_candidate_cve_count": sum(
            x["patch_availability"] != "NO_FIXED_VERSION_IN_SCAN"
            for x in entries
        ),
        "entries": entries,
        "human_review": "REQUIRED",
        "security_release_verdict": "NO_GO",
        "scientific_verdict": "NOT_EVALUATED",
        "release_approval": "NOT_GRANTED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink():
            raise TriageContractError("Triage output already exists")
        raw = args.scan.read_bytes()
        obj = json.loads(raw.decode("utf-8"))
        result = make_triage_report(
            obj,
            source_sha=args.source_sha,
            image_id=args.image_id,
            scan_sha256=hashlib.sha256(raw).hexdigest(),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, sort_keys=True, indent=2, ensure_ascii=False)
            stream.write("\n")
        print(
            "CVE triage report saved; human review required, release NO_GO "
            f"({result['unique_cve_count']} unique CVEs)"
        )
        return 0
    except (TriageContractError, OSError, UnicodeError, ValueError, TypeError) as exc:
        print(f"CVE triage: FAIL ({type(exc).__name__})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
