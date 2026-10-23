"""Validate a human-reviewed editor session bound to exact artifact bytes.

This validates the attestation and integrity, not autonomous GUI observation.
"""

import hashlib
from datetime import datetime

from ifc_to_fds.domain.validation import GateResult, GateStatus


def validate_editor_evidence(document, source, exported, artifacts):
    evidence = {
        "method": "HUMAN_REVIEW_WITH_HASH_BOUND_ARTIFACTS",
        "gui_automated": False,
    }

    def fail(reason):
        return GateResult(status=GateStatus.FAIL, reason=reason, evidence=evidence)

    if not isinstance(document, dict):
        return fail("Editor review must be a JSON object")
    for key in ("pyrosim_version", "reviewer", "warnings_review", "imported_at"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            return fail(f"Editor review requires {key}")
    try:
        timestamp = datetime.fromisoformat(
            document["imported_at"].replace("Z", "+00:00")
        )
        if timestamp.tzinfo is None:
            return fail("Editor session timestamp must include a timezone")
    except ValueError:
        return fail("Invalid editor session timestamp")
    if document.get("import_result") != "IMPORTED":
        return fail("Reviewer did not confirm successful import")
    for key, data in (("source_sha256", source), ("exported_sha256", exported)):
        if document.get(key) != hashlib.sha256(data).hexdigest():
            return fail(f"Editor session refers to different bytes: {key}")
    for key in ("project", "diagnostics"):
        item = document.get(key)
        data = artifacts.get(key)
        if (
            not isinstance(item, dict)
            or not data
            or item.get("sha256") != hashlib.sha256(data).hexdigest()
        ):
            return fail(f"Missing or changed editor evidence: {key}")
    evidence.update(document)
    evidence.update(
        method="HUMAN_REVIEW_WITH_HASH_BOUND_ARTIFACTS", gui_automated=False
    )
    return GateResult(
        status=GateStatus.PASS,
        reason="Reviewer attests successful PyroSim import; source, re-export, project and diagnostics hashes match",
        evidence=evidence,
    )
