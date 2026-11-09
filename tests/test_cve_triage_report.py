"""Regression cho sổ CVE: metadata/provenance, grouping và fail-closed."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "triage-release-vulnerabilities.py"
SPEC = importlib.util.spec_from_file_location("ifctofds_cve_triage", SOURCE)
assert SPEC is not None and SPEC.loader is not None
triage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(triage)
SHA = "a" * 40
IMAGE = "sha256:" + "b" * 64
SCAN_HASH = "c" * 64


def _scan():
    return {
        "SchemaVersion": 2,
        "ArtifactName": "ifctofds:security",
        "ArtifactType": "container_image",
        "CreatedAt": "2026-11-09T00:00:00Z",
        "Metadata": {
            "ImageID": IMAGE,
            "OS": {"Family": "debian", "Name": "13.7"},
        },
        "Results": [{
            "Target": "ifctofds:security (debian 13.7)",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2026-109518",
                    "PkgName": "apt",
                    "InstalledVersion": "3.0.3",
                    "FixedVersion": "3.0.4",
                    "Severity": "HIGH",
                    "Status": "fixed",
                },
                {
                    "VulnerabilityID": "CVE-2026-109518",
                    "PkgName": "libapt-pkg7.0",
                    "InstalledVersion": "3.0.3",
                    "FixedVersion": "3.0.4",
                    "Severity": "HIGH",
                    "Status": "fixed",
                },
                {
                    "VulnerabilityID": "CVE-2026-76642",
                    "PkgName": "util-linux",
                    "InstalledVersion": "2.41",
                    "Severity": "HIGH",
                    "Status": "affected",
                },
            ],
        }],
    }


def _report(scan):
    return triage.make_triage_report(
        scan, source_sha=SHA, image_id=IMAGE, scan_sha256=SCAN_HASH
    )


def test_groups_by_cve_without_converting_findings_to_unique_cves():
    record = _report(_scan())
    assert record["finding_counts"] == {"HIGH": 3, "CRITICAL": 0}
    assert record["unique_cve_count"] == 2
    assert record["patch_candidate_cve_count"] == 1
    assert record["entries"][0]["cve_id"] == "CVE-2026-109518"
    assert record["entries"][0]["findings_count"] == 2
    assert record["entries"][0]["patch_availability"] == "ALL_FINDINGS_HAVE_FIXED_VERSION"
    assert record["entries"][1]["patch_availability"] == "NO_FIXED_VERSION_IN_SCAN"
    assert all(e["triage_status"] == "UNREVIEWED" for e in record["entries"])
    assert record["security_release_verdict"] == "NO_GO"
    assert record["scientific_verdict"] == "NOT_EVALUATED"
    assert record["release_approval"] == "NOT_GRANTED"


def test_no_findings_does_not_grant_release_approval():
    scan = _scan()
    scan["Results"][0]["Vulnerabilities"] = []
    result = _report(scan)
    assert result["unique_cve_count"] == 0
    assert result["security_release_verdict"] == "NO_GO"
    assert result["human_review"] == "REQUIRED"


@pytest.mark.parametrize("bad", ["source", "image", "scan_hash", "scanner_id", "scanner_type"])
def test_rejects_broken_provenance(bad):
    scan = _scan()
    if bad == "scanner_id":
        scan["Metadata"]["ImageID"] = "sha256:" + "f" * 64
    elif bad == "scanner_type":
        scan["ArtifactType"] = "filesystem"
    with pytest.raises(triage.TriageContractError):
        triage.make_triage_report(
            scan,
            source_sha="wrong" if bad == "source" else SHA,
            image_id="bad-id" if bad == "image" else IMAGE,
            scan_sha256="x" if bad == "scan_hash" else SCAN_HASH,
        )


@pytest.mark.parametrize("field,invalid", [
    ("VulnerabilityID", "NOT-A-CVE"),
    ("Severity", "LOW"),
    ("PkgName", ""),
    ("InstalledVersion", None),
])
def test_rejects_unsupported_or_incomplete_findings(field, invalid):
    scan = _scan()
    scan["Results"][0]["Vulnerabilities"][0][field] = invalid
    with pytest.raises(triage.TriageContractError):
        _report(scan)


def test_missing_results_and_malformed_json_fail_closed():
    scan = _scan()
    del scan["Results"]
    with pytest.raises(triage.TriageContractError, match="Missing scanner Results"):
        _report(scan)


def test_cli_writes_hashed_evidence_once_without_auto_approval(tmp_path, capsys):
    scan = tmp_path / "vulnerabilities.json"
    raw = json.dumps(_scan()).encode("utf-8")
    scan.write_bytes(raw)
    output = tmp_path / "triage" / "report.json"
    argv = [
        "--scan", str(scan), "--output", str(output),
        "--source-sha", SHA, "--image-id", IMAGE,
    ]
    assert triage.main(argv) == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["scan_sha256"] == hashlib.sha256(raw).hexdigest()
    assert data["release_approval"] == "NOT_GRANTED"
    assert triage.main(argv) == 2
    assert data == json.loads(output.read_text(encoding="utf-8"))
    assert "CVE triage: FAIL" in capsys.readouterr().err
