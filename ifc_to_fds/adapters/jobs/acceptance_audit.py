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

from ifc_to_fds.geometry.package_integrity import verify_package_metadata
from ifc_to_fds.geometry.storage import file_hash

from .evidence_index import verify_evidence_index
from .result_contract import validate_job_result

JobMode = Literal["convert", "scenario", "preview", "inventory"]


def _check(status: str, detail: str) -> dict[str, str]:
    return {"status": status, "detail": detail}


def _verify_geometry_payloads(directory: Path) -> int:
    """Verify each referenced disk payload once, without loading mesh arrays.

    The index hash is validated separately. This check is of persisted bytes
    and reference metadata only, not manifoldness or scientific accuracy.
    """
    index_path = directory / "model_geometry.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        verify_package_metadata(index)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("Geometry index is unreadable or inconsistent") from exc
    if index.get("storage_format") != "float64-uint32-le-v1":
        raise ValueError("Unsupported disk-backed geometry payload format")
    elements = index["elements"]
    if not isinstance(elements, dict):
        raise ValueError("Geometry elements must be an object")
    validated: set[str] = set()
    for entry in elements.values():
        if not isinstance(entry, dict):
            raise ValueError("Geometry element entry is invalid")
        openings = entry.get("openings", {})
        if not isinstance(openings, dict):
            raise ValueError("Geometry openings must be an object")
        for ref in (entry.get("mesh"), *openings.values()):
            if ref is None:
                continue
            if not isinstance(ref, dict):
                raise ValueError("Geometry payload reference is invalid")
            identity = ref.get("payload")
            if (
                not isinstance(identity, str)
                or len(identity) != 64
                or any(ch not in "0123456789abcdef" for ch in identity)
            ):
                raise ValueError("Geometry payload identity is invalid")
            vertices = ref.get("vertex_count")
            faces = ref.get("face_count")
            if (
                type(vertices) is not int or type(faces) is not int
                or min(vertices, faces) < 0
            ):
                raise ValueError("Geometry payload dimensions are invalid")
            expected = vertices * 24 + faces * 12
            offsets = (
                ref.get("vertices_offset"), ref.get("faces_offset"),
                ref.get("byte_length"),
            )
            if (
                any(type(value) is not int for value in offsets)
                or offsets != (0, vertices * 24, expected)
            ):
                raise ValueError("Geometry payload offsets are inconsistent")
            payload = index_path.with_suffix(".payloads") / (identity + ".bin")
            try:
                if not payload.is_file() or payload.stat().st_size != expected:
                    raise ValueError("Geometry payload is missing or truncated")
                if identity not in validated:
                    if file_hash(payload) != identity:
                        raise ValueError("Geometry payload SHA-256 differs")
                    validated.add(identity)
            except OSError as exc:
                raise ValueError("Geometry payload became unreadable") from exc
    return len(validated)


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
        "geometry_payload_integrity": _check(
            "NOT_RUN", "Geometry payload bytes have not been checked"
        ),
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
    claimed_verdict = result.get("verdict", result.get("status"))
    # Do not echo arbitrary untrusted nested JSON in a diagnostic report.
    if isinstance(claimed_verdict, str) and len(claimed_verdict) <= 64:
        report["reported_verdict"] = claimed_verdict
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
        checks["geometry_payload_integrity"] = _check(
            "NOT_APPLICABLE",
            "Geometry payload verification is outside this preview/inventory audit",
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
    if mode == "convert" and "geometry" in result["artifacts"]:
        try:
            verified_count = _verify_geometry_payloads(path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            checks["geometry_payload_integrity"] = _check(
                "FAIL",
                f"Geometry payloads are incomplete or changed: {type(exc).__name__}",
            )
            return report
        checks["geometry_payload_integrity"] = _check(
            "PASS", f"Checked {verified_count} unique disk payload digests"
        )
    else:
        checks["geometry_payload_integrity"] = _check(
            "NOT_APPLICABLE", "No disk geometry payload artifact is declared"
        )
    report["audit_outcome"] = "EVIDENCE_VALID"
    return report
