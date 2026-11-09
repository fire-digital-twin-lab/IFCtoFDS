"""Contract tests for fail-closed GHCR release candidate pipeline."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-candidate.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_candidate_workflow_is_manual_and_requires_main_approval():
    content = _workflow()
    assert "on:\n  workflow_dispatch:" in content
    assert "approve_candidate:" in content
    assert "default: false" in content
    assert "github.ref == 'refs/heads/main' && inputs.approve_candidate" in content
    assert "environment: release-candidate" in content
    assert "concurrency:" in content
    assert "cancel-in-progress: false" in content
    assert "permissions: {}" in content
    assert "packages: write" in content
    assert "id-token: write" in content
    assert "attestations: write" in content


def test_candidate_never_authenticates_or_pushes_before_scanner_enforcement():
    content = _workflow()
    required = [
        "Build a single local candidate image",
        "Generate SBOM for candidate bytes",
        "Scan the exact same local candidate",
        "Enforce security gate BEFORE any registry access",
        "Authenticate to GHCR only after security PASS",
        "Publish EXACT previously scanned image and record digest",
        "Sign provenance for the pushed OCI digest",
    ]
    offsets = [content.index(name) for name in required]
    assert offsets == sorted(offsets)
    assert "docker build --pull -t ifctofds:security ." in content
    assert "image: ifctofds:security" in content
    assert "image-ref: ifctofds:security" in content
    assert "scripts/validate-release-security-evidence.py" in content
    assert "--enforce" in content
    assert "docker tag ifctofds:security" in content
    assert "docker push" in content
    assert "docker manifest inspect" in content
    assert "push-to-registry: true" in content


def test_candidate_records_digest_but_does_not_claim_release_or_deployment():
    content = _workflow()
    assert "subject-name: ghcr.io/fire-digital-twin-lab/ifctofds" in content
    assert "subject-digest: ${{ steps.push.outputs.digest }}" in content
    assert "attestation_url" in content
    assert '"release_approval": "NOT_GRANTED"' in content
    assert '"production_deployed": False' in content
    assert "release-candidate-evidence" in content
    assert "retention-days: 90" in content
    assert "if: always()" in content
    assert not re.search(r"\bcurl\s+-k\b", content)


def test_candidate_uses_pinned_full_shas_for_supply_chain_actions():
    content = _workflow()
    expected = [
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
        "anchore/sbom-action@66cbf4bc1f1c0d2edc94016e65bc221b6bb0ad6c",
        "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25",
        "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
    ]
    for action in expected:
        assert action in content
