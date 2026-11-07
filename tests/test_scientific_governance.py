from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "science" / "SCIENTIFIC_CLAIMS.md"
SCHEMA = ROOT / "docs" / "science" / "evidence-manifest.schema.json"

VERDICTS = {"PASS", "FAIL", "INCONCLUSIVE", "NOT_APPLICABLE"}
EVIDENCE_LEVELS = {f"E{i}" for i in range(7)}
REQUIRED_FIELDS = {
    "statement",
    "intended_use",
    "affected_modules",
    "evidence_level",
    "supporting_evidence",
    "known_limitations",
    "validation_domain",
    "status",
    "reviewer",
}
CLAIM_HEADING = re.compile(r"^## Claim `(?P<claim_id>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)`$", re.MULTILINE)
FIELD = re.compile(r"^- \*\*(?P<key>[a-z_]+)\*\*: (?P<value>.+)$", re.MULTILINE)


def _claims() -> dict[str, dict[str, str]]:
    text = LEDGER.read_text(encoding="utf-8")
    headings = list(CLAIM_HEADING.finditer(text))
    assert headings, "scientific claim ledger must contain at least one claim"
    claims: dict[str, dict[str, str]] = {}
    for index, heading in enumerate(headings):
        claim_id = heading.group("claim_id")
        assert claim_id not in claims, f"duplicate scientific claim id: {claim_id}"
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[heading.end():end]
        pairs = FIELD.findall(section)
        fields = dict(pairs)
        assert len(pairs) == len(fields), f"{claim_id}: duplicate field"
        assert set(fields) == REQUIRED_FIELDS, (
            f"{claim_id}: fields differ; missing={sorted(REQUIRED_FIELDS - set(fields))}, "
            f"extra={sorted(set(fields) - REQUIRED_FIELDS)}"
        )
        claims[claim_id] = fields
    return claims


def test_scientific_claim_ledger_is_fail_closed() -> None:
    claims = _claims()
    for claim_id, fields in claims.items():
        assert fields["status"] in VERDICTS, f"{claim_id}: invalid verdict"
        assert fields["evidence_level"] in EVIDENCE_LEVELS, f"{claim_id}: invalid evidence level"
        assert fields["reviewer"].strip(), f"{claim_id}: reviewer must be explicit"
        assert fields["known_limitations"].strip(), f"{claim_id}: limitations must be explicit"
        assert fields["validation_domain"].strip(), f"{claim_id}: validation domain must be explicit"
        if fields["status"] == "PASS":
            assert fields["evidence_level"] != "E0", f"{claim_id}: E0 cannot support PASS"
            normalized = fields["supporting_evidence"].lower()
            assert normalized not in {"none", "n/a", "pending"}, (
                f"{claim_id}: PASS requires concrete supporting evidence"
            )


def test_claims_requiring_independent_review_do_not_claim_pass() -> None:
    claims = _claims()
    for claim_id, fields in claims.items():
        if fields["reviewer"] == "PENDING_INDEPENDENT_REVIEW":
            assert fields["status"] != "PASS", (
                f"{claim_id}: independent review is pending, so PASS is not permitted"
            )


def test_scientific_evidence_manifest_schema_uses_project_enums() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = set(schema["required"])
    assert {
        "run_id",
        "timestamp_utc",
        "git",
        "environment",
        "inputs",
        "configuration",
        "commands",
        "claims",
        "artifacts",
        "overall_verdict",
        "known_limitations",
    } <= required
    assert set(schema["$defs"]["verdict"]["enum"]) == VERDICTS
    assert set(schema["$defs"]["evidenceLevel"]["enum"]) == EVIDENCE_LEVELS
    assert schema["properties"]["git"]["properties"]["sha"]["pattern"] == "^[0-9a-f]{40}$"
    assert schema["$defs"]["sha256"]["pattern"] == "^[0-9a-f]{64}$"
