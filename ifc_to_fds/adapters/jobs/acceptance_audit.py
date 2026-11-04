"""Read-only acceptance-evidence audit for persisted IFCtoFDS jobs.

This audit verifies JSON contracts and available content hashes. It never
executes the CFD solver and never upgrades a reported scientific verdict.
A green evidence audit is NOT equivalent to MAPPING_VERIFIED or
SIMULATION_VERIFIED.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from .evidence_index import verify_evidence_index
from .result_contract import validate_job_result

JobMode = Literal["convert", "scenario", "preview", "inventory"]


def _check(status: str, detail: str) -> dict[str, str]:
    return {"status": status, "detail": detail}


def audit_persisted_job(directory: str | Path, mode: JobMode) -> dict[str, Any]:
    """Audit a saved job directory without changing any file or job state.

    Check results refer to *data/contract* integrity, not engineering approval.
    A conversion result may remain REJECTED even if its audit evidence is intact.
    """
    path = Path(directory)
    checks: dict[str, dict[str, str]] = {
        "result_json": _check("NOT_RUN", "result.json has not been read"),
        "result_contract": _check("NOT_RUN", "Contract has not been checked"),
        "evidence_integrity": _check("NOT_RUN", "Evidence has not been checked"),
        "solver_verification": _check(
            "NOT_RUN", "Independent CFD solver verification was not performed"
        ),
    }
    report: dict[str, Any] = {
        "audit_schema_version": 1,
        "mode": mode,
        "checks": checks,
        "reported_verdict": None,
        "audit_outcome": "INTEGRITY_INVALID",
        "scientific_acceptance": "NOT_ESTABLISHED_BY_THIS_AUDIT",
    }
    try:
        result = json.loads((path / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        checks["result_json"] = _check(
            "FAIL", f"Cannot read persisted result.json: {type(exc).__name__}"
        )
        return report
    if not isinstance(result, dict):
        checks["result_json"] = _check("FAIL", "result.json must be an object")
        return report
    checks["result_json"] = _check("PASS", "Persisted JSON object is readable")
    report["reported_verdict"] = result.get("verdict", result.get("status"))
    try:
        validate_job_result(mode, result)
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        checks["result_contract"] = _check(
            "FAIL", f"Result violates the {mode} contract: {type(exc).__name__}"
        )
        return report
    checks["result_contract"] = _check(
        "PASS", f"Mode-specific {mode} result schema is consistent"
    )

    if mode in ("preview", "inventory"):
        checks["evidence_integrity"] = _check(
            "NOT_APPLICABLE",
            "No published convert/scenario content-addressed evidence index",
        )
        report["audit_outcome"] = "STRUCTURE_VALID"
        return report

    try:
        verify_evidence_index(path, mode, result)
    except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        checks["evidence_integrity"] = _check(
            "FAIL", f"Persisted evidence failed integrity check: {type(exc).__name__}"
        )
        return report
    checks["evidence_integrity"] = _check(
        "PASS",
        "Declared persisted bytes and supported cross-file evidence agree",
    )
    report["audit_outcome"] = "EVIDENCE_VALID"
    return report
