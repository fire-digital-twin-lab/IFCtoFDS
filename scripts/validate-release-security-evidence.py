"""Tạo hồ sơ SBOM/CVE có provenance cho image CI; không tự phê duyệt release.

Quy trình mặc định kiểm tra định dạng, checksum và tính nhất quán artifact.
--enforce thực thi ngưỡng không cho phép HIGH/CRITICAL, dành cho release gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_EXPECTED_REF = "ifctofds:security"


class ReleaseEvidenceError(ValueError):
    """Hồ sơ bảo mật image chưa đáp ứng contract."""


def _read_json_object(path: Path) -> dict:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ReleaseEvidenceError("Cannot read valid JSON evidence") from exc
    if not isinstance(content, dict):
        raise ReleaseEvidenceError("Expected JSON evidence object")
    return content


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise ReleaseEvidenceError("Cannot hash evidence file") from exc
    return digest.hexdigest()


def _check_sbom(value: dict) -> int:
    if value.get("spdxVersion") != "SPDX-2.3":
        raise ReleaseEvidenceError("SBOM must be SPDX-2.3 JSON")
    packages = value.get("packages")
    if not isinstance(packages, list) or not packages:
        raise ReleaseEvidenceError("SBOM does not contain packages")
    if not all(isinstance(item, dict) and item.get("SPDXID") for item in packages):
        raise ReleaseEvidenceError("Malformed SPDX package entry")
    return len(packages)


def _check_scan(value: dict, image_id: str) -> dict:
    if value.get("SchemaVersion") != 2:
        raise ReleaseEvidenceError("Expected Trivy SchemaVersion 2")
    if value.get("ArtifactName") != _EXPECTED_REF or value.get("ArtifactType") != "container_image":
        raise ReleaseEvidenceError("Scan does not identify the expected container image")
    results = value.get("Results")
    if not isinstance(results, list):
        raise ReleaseEvidenceError("Trivy Results must be an array")
    metadata = value.get("Metadata", {})
    if not isinstance(metadata, dict):
        raise ReleaseEvidenceError("Invalid scanner Metadata")
    scanned_id = metadata.get("ImageID")
    if scanned_id is not None and scanned_id != image_id:
        raise ReleaseEvidenceError("Scanned image ID differs from built image")
    counts = {severity: 0 for severity in ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")}
    for result in results:
        if not isinstance(result, dict):
            raise ReleaseEvidenceError("Invalid Trivy result")
        vulnerabilities = result.get("Vulnerabilities") or []
        if not isinstance(vulnerabilities, list):
            raise ReleaseEvidenceError("Trivy Vulnerabilities must be an array")
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                raise ReleaseEvidenceError("Invalid vulnerability finding")
            severity = vulnerability.get("Severity")
            if severity not in counts or not vulnerability.get("VulnerabilityID"):
                raise ReleaseEvidenceError("Invalid severity or missing vulnerability ID")
            counts[severity] += 1
    return {"counts": counts, "image_id_verified": scanned_id == image_id}


def build_evidence(
    sbom_path: Path,
    scan_path: Path,
    *,
    source_sha: str,
    image_id: str,
    enforce: bool = False,
) -> dict:
    if not _SHA40.fullmatch(source_sha) or not _IMAGE_ID.fullmatch(image_id):
        raise ReleaseEvidenceError("Source SHA or local image ID has invalid format")
    count = _check_sbom(_read_json_object(sbom_path))
    scan = _check_scan(_read_json_object(scan_path), image_id)
    blockers = scan["counts"]["HIGH"] + scan["counts"]["CRITICAL"]
    report = {
        "schema": 1,
        "source_sha": source_sha,
        "local_image_id": image_id,
        "image_ref": _EXPECTED_REF,
        "sbom_sha256": _hash(sbom_path),
        "scan_sha256": _hash(scan_path),
        "sbom_packages": count,
        "vulnerabilities": scan["counts"],
        "scanner_image_id_verified": scan["image_id_verified"],
        "security_policy": "REJECT_HIGH_AND_CRITICAL" if enforce else "EVIDENCE_ONLY",
        "security_gate": "PASS" if enforce and not blockers else (
            "FAIL" if enforce else "NOT_ENFORCED"
        ),
        "release_approval": "NOT_GRANTED",
        "registry_digest": None,
        "staging_approval": "NOT_RUN",
    }
    if enforce and blockers:
        raise ReleaseEvidenceError(
            "HIGH or CRITICAL vulnerabilities prohibit security approval"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sbom", required=True, type=Path)
    parser.add_argument("--scan", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_evidence(
            args.sbom,
            args.scan,
            source_sha=args.source_sha,
            image_id=args.image_id,
            enforce=args.enforce,
        )
        if args.output.exists():
            raise ReleaseEvidenceError("Evidence output already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print("Image security evidence: VALID (release not approved)")
        return 0
    except (ReleaseEvidenceError, OSError) as exc:
        # Không in nội dung SBOM hoặc token, chỉ cung cấp lỗi contract.
        print(f"Image security evidence: FAIL ({exc})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
