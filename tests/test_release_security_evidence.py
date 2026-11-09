"""Kiểm thử hồ sơ SBOM/CVE, integrity và fail-closed release gate."""

import importlib.util
import json
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "validate-release-security-evidence.py"
SPEC = importlib.util.spec_from_file_location("ifctofds_release_security_evidence", SOURCE)
assert SPEC is not None and SPEC.loader is not None
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


SOURCE_SHA = "a" * 40
IMAGE_ID = "sha256:" + "b" * 64


def _fixtures(tmp_path, *, severity=None, scanned_image_id=IMAGE_ID):
    sbom = tmp_path / "image.spdx.json"
    sbom.write_text(
        json.dumps({
            "spdxVersion": "SPDX-2.3",
            "packages": [{"SPDXID": "SPDXRef-Package-python", "name": "python"}],
        }),
        encoding="utf-8",
    )
    scan = tmp_path / "vulnerabilities.json"
    findings = (
        [{"VulnerabilityID": "CVE-TEST-0001", "Severity": severity}]
        if severity is not None else []
    )
    scan.write_text(
        json.dumps({
            "SchemaVersion": 2,
            "ArtifactName": "ifctofds:security",
            "ArtifactType": "container_image",
            "Metadata": {"ImageID": scanned_image_id},
            "Results": [{"Target": "os", "Vulnerabilities": findings}],
        }),
        encoding="utf-8",
    )
    return sbom, scan


def test_inventory_collects_hashes_without_claiming_release_approval(tmp_path):
    sbom, scan = _fixtures(tmp_path, severity="HIGH")
    record = evidence.build_evidence(
        sbom, scan, source_sha=SOURCE_SHA, image_id=IMAGE_ID
    )
    assert record["security_gate"] == "NOT_ENFORCED"
    assert record["release_approval"] == "NOT_GRANTED"
    assert record["registry_digest"] is None
    assert record["scanner_image_id_verified"] is True
    assert record["vulnerabilities"]["HIGH"] == 1
    assert len(record["sbom_sha256"]) == 64
    assert len(record["scan_sha256"]) == 64


@pytest.mark.parametrize("severity", ["CRITICAL", "HIGH"])
def test_enforced_gate_rejects_high_and_critical_findings(tmp_path, severity):
    sbom, scan = _fixtures(tmp_path, severity=severity)
    with pytest.raises(evidence.ReleaseEvidenceError, match="prohibit"):
        evidence.build_evidence(
            sbom, scan, source_sha=SOURCE_SHA, image_id=IMAGE_ID, enforce=True
        )


def test_enforced_gate_accepts_clean_image_but_not_global_release(tmp_path):
    sbom, scan = _fixtures(tmp_path)
    report = evidence.build_evidence(
        sbom, scan, source_sha=SOURCE_SHA, image_id=IMAGE_ID, enforce=True
    )
    assert report["security_gate"] == "PASS"
    assert report["release_approval"] == "NOT_GRANTED"
    assert report["staging_approval"] == "NOT_RUN"


@pytest.mark.parametrize("broken", ["sha", "image", "scanner"])
def test_mismatched_provenance_fails_closed(tmp_path, broken):
    sbom, scan = _fixtures(
        tmp_path,
        scanned_image_id="sha256:" + "f" * 64 if broken == "scanner" else IMAGE_ID,
    )
    with pytest.raises(evidence.ReleaseEvidenceError):
        evidence.build_evidence(
            sbom, scan,
            source_sha="bad" if broken == "sha" else SOURCE_SHA,
            image_id="sha256:invalid" if broken == "image" else IMAGE_ID,
        )


def test_empty_packages_and_malformed_scan_are_rejected(tmp_path):
    sbom, scan = _fixtures(tmp_path)
    sbom.write_text(json.dumps({"spdxVersion": "SPDX-2.3", "packages": []}))
    with pytest.raises(evidence.ReleaseEvidenceError, match="does not contain packages"):
        evidence.build_evidence(
            sbom, scan, source_sha=SOURCE_SHA, image_id=IMAGE_ID
        )
    sbom.write_text(json.dumps({
        "spdxVersion": "SPDX-2.3",
        "packages": [{"SPDXID": "SPDXRef-Package-python"}],
    }))
    scan.write_text(json.dumps({"SchemaVersion": 2, "Results": []}))
    with pytest.raises(evidence.ReleaseEvidenceError, match="expected container image"):
        evidence.build_evidence(
            sbom, scan, source_sha=SOURCE_SHA, image_id=IMAGE_ID
        )


def test_cli_writes_once_and_prevents_overwriting_existing_evidence(tmp_path, capsys):
    sbom, scan = _fixtures(tmp_path)
    target = tmp_path / "release" / "summary.json"
    argv = [
        "--sbom", str(sbom), "--scan", str(scan),
        "--source-sha", SOURCE_SHA, "--image-id", IMAGE_ID,
        "--output", str(target),
    ]
    assert evidence.main(argv) == 0
    saved = json.loads(target.read_text())
    assert saved["security_gate"] == "NOT_ENFORCED"
    assert evidence.main(argv) == 2
    assert saved == json.loads(target.read_text())
    assert "already exists" in capsys.readouterr().err
