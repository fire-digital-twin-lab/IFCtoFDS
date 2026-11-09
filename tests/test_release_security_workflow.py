"""Hợp đồng CI image-security: scan đúng image, pin action và fail-closed evidence."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_security_workflow_builds_and_scans_the_same_runtime_image():
    workflow = (ROOT / ".github" / "workflows" / "release-security.yml").read_text(
        encoding="utf-8"
    )
    assert "docker build --pull -t ifctofds:security ." in workflow
    assert "image: ifctofds:security" in workflow
    assert "image-ref: ifctofds:security" in workflow
    assert "format: spdx-json" in workflow
    assert "format: json" in workflow
    assert "output-file: release-evidence/image.spdx.json" in workflow
    assert "output: release-evidence/vulnerabilities.json" in workflow
    assert "scripts/validate-release-security-evidence.py" in workflow
    assert "SOURCE_SHA: ${{ github.sha }}" in workflow


def test_third_party_security_actions_are_pinned_to_full_commit_sha():
    workflow = (ROOT / ".github" / "workflows" / "release-security.yml").read_text(
        encoding="utf-8"
    )
    assert "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683" in workflow
    assert "anchore/sbom-action@66cbf4bc1f1c0d2edc94016e65bc221b6bb0ad6c" in workflow
    assert "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" in workflow
    assert "contents: read" in workflow
    assert "permissions:" in workflow
    assert "retention-days: 30" in workflow


def test_inventory_does_not_masquerade_as_release_approval():
    workflow = (ROOT / ".github" / "workflows" / "release-security.yml").read_text(
        encoding="utf-8"
    )
    documentation = (ROOT / "deploy" / "RELEASE_SECURITY_EVIDENCE.md").read_text(
        encoding="utf-8"
    )
    assert "exit-code: '0'" in workflow  # Evidence-only, policy là giai đoạn riêng.
    assert "workflow_dispatch" in workflow
    assert "--enforce" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.enforce" in workflow
    assert "EVIDENCE_ONLY" in documentation
    assert "NOT_PRODUCTION_READY" in documentation
    assert "build once" in documentation


def test_os_security_patches_are_pinned_and_verified_in_runtime():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    container = (ROOT / ".github" / "workflows" / "container.yml").read_text(
        encoding="utf-8"
    )
    assert "apt=3.0.4" in dockerfile
    assert "libapt-pkg7.0=3.0.4" in dockerfile
    assert "zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1" in dockerfile
    assert "apt-get update" in dockerfile
    assert "Verify exact Debian security package versions inside production image" in container
    assert "dpkg-query -W" in container
    assert "--read-only --entrypoint sh ifctofds:ci" in container


def test_scanner_denies_known_patched_cves_in_both_validation_modes():
    workflow = (ROOT / ".github" / "workflows" / "release-security.yml").read_text(
        encoding="utf-8"
    )
    for cve in ("CVE-2026-109518", "CVE-2026-76844", "CVE-2026-85091"):
        assert workflow.count(f"--deny-cve {cve}") == 2
    assert "exit-code: '0'" in workflow  # Khác strict release: vẫn thống kê HIGH.
