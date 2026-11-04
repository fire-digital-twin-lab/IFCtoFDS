"""R10-08 — content-addressed evidence index for persisted job results.

This is an integrity and cross-file consistency check, not a digital signature
or an independent scientific verification. Every new convert/scenario job
must publish the index before its worker exits successfully.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from ifc_to_fds.domain.mapping import MappingManifest
from ifc_to_fds.results import ARTIFACTS

EVIDENCE_FILENAME = "result_evidence.json"
SCHEMA_VERSION = 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot parse required evidence file {path.name}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"Evidence file {path.name} is not an object")
    return obj


def _required_files(mode: str, result: dict[str, Any]) -> set[str]:
    if mode == "scenario":
        return {"scenario.fds"}
    if mode == "convert" and result["status"] == "MAPPING_VERIFIED":
        return {
            "model.fds", "model_manifest.json", "model_acceptance_report.json",
            "model_geometry.json", "audit-state.json",
        }
    return set()


def _selected_files(mode: str, result: dict[str, Any]) -> set[str]:
    names = {"result.json"} | _required_files(mode, result)
    if mode not in ("convert", "scenario"):
        return names
    for name in result["artifacts"]:
        filename = ARTIFACTS.get(name)
        if filename is None:
            raise ValueError(f"Unknown evidence artifact key {name!r}")
        names.add(filename)
    return names


def _validate_linked_content(
    directory: Path, mode: str, result: dict[str, Any], digests: dict[str, str]
) -> None:
    """Check evidence consistency without modifying scientific gate decisions."""
    if mode == "scenario":
        actual = digests["scenario.fds"]
        if actual != result["evidence"]["fds_sha256"]:
            raise ValueError("Scenario FDS bytes differ from declared evidence SHA-256")
        return

    if mode != "convert":
        return

    # Check available report/manifest verdicts even when the final verdict
    # is INCONCLUSIVE or REJECTED. A non-PASS result is not an exemption from
    # cross-file consistency checks.
    artifacts = result["artifacts"]
    manifest = (
        _read_object(directory / "model_manifest.json")
        if "manifest" in artifacts else None
    )
    report = (
        _read_object(directory / "model_acceptance_report.json")
        if "report" in artifacts else None
    )
    if manifest is not None:
        for field, expected in (
            ("acceptance_status", result["status"]),
            ("mapping_acceptance", result["mapping_status"]),
            ("simulation_acceptance", result["simulation_status"]),
            ("output_complete", result["output_complete"]),
        ):
            if manifest.get(field) != expected:
                raise ValueError(f"Manifest {field} contradicts result.json")
    if report is not None:
        for field in ("status", "mapping_status", "simulation_status"):
            if report.get(field) != result[field]:
                raise ValueError(f"Acceptance report {field} contradicts result.json")
    if result["status"] != "MAPPING_VERIFIED":
        return

    if manifest is None or report is None:
        raise ValueError("Verified mapping is missing report or manifest")
    checkpoint = _read_object(directory / "audit-state.json")
    geometry = _read_object(directory / "model_geometry.json")
    if (
        checkpoint.get("status") != "MAPPING_VERIFIED"
        or checkpoint.get("checkpoint_status") != "VERIFIED_SEALED"
        or checkpoint.get("output_complete") is not True
        or checkpoint.get("bundle_sha256") != manifest.get("bundle_sha256")
    ):
        raise ValueError("Verified checkpoint is missing or contradictory")
    if digests["model.fds"] != manifest.get("fds_sha256"):
        raise ValueError("FDS bytes differ from the verified manifest digest")
    if geometry.get("sha256") != manifest.get("geometry_package_sha256"):
        raise ValueError("Geometry index differs from the verified manifest")
    parsed = MappingManifest.model_validate(manifest)
    if parsed.compute_bundle_sha256() != parsed.bundle_sha256:
        raise ValueError("Verified bundle hash does not match manifest contents")


def build_evidence_index(
    directory: str | Path, mode: str, result: dict[str, Any]
) -> dict[str, Any]:
    """Build index after result and artifact files exist, without persisting it."""
    if mode not in ("convert", "scenario"):
        raise ValueError("Evidence indexing is currently defined for convert/scenario")
    directory = Path(directory)
    files = {}
    for filename in sorted(_selected_files(mode, result)):
        path = directory / filename
        if not path.is_file():
            raise ValueError(f"Missing required job evidence file: {filename}")
        files[filename] = _sha256(path)
    _validate_linked_content(directory, mode, result, files)
    return {"schema_version": SCHEMA_VERSION, "mode": mode, "files": files}


def write_evidence_index(
    directory: str | Path, mode: str, result: dict[str, Any]
) -> None:
    directory = Path(directory)
    index = build_evidence_index(directory, mode, result)
    destination = directory / EVIDENCE_FILENAME
    staging = directory / (EVIDENCE_FILENAME + "." + uuid4().hex + ".tmp")
    try:
        staging.write_text(json.dumps(index, sort_keys=True), encoding="utf-8")
        staging.replace(destination)
    finally:
        staging.unlink(missing_ok=True)


def verify_evidence_index(
    directory: str | Path, mode: str, result: dict[str, Any]
) -> None:
    """Require and validate index, including its own file-set completeness."""
    if mode not in ("convert", "scenario"):
        return
    directory = Path(directory)
    if not (directory / EVIDENCE_FILENAME).is_file():
        raise ValueError(
            "Missing evidence index: historical or incomplete job; "
            "read-only provenance review required before recovery"
        )
    index = _read_object(directory / EVIDENCE_FILENAME)
    if index.get("schema_version") != SCHEMA_VERSION or index.get("mode") != mode:
        raise ValueError("Evidence index schema or job mode mismatch")
    files = index.get("files")
    if not isinstance(files, dict) or set(files) != _selected_files(mode, result):
        raise ValueError("Evidence file-set differs from result artifact declarations")
    for filename, digest in files.items():
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError(f"Invalid digest for {filename}")
        path = directory / filename
        try:
            valid = path.is_file() and _sha256(path) == digest
        except OSError as exc:
            raise ValueError(
                f"Evidence file unreadable during verification: {filename}"
            ) from exc
        if not valid:
            raise ValueError(f"Evidence file changed or missing: {filename}")
    try:
        _validate_linked_content(directory, mode, result, files)
    except OSError as exc:
        raise ValueError("Evidence files disappeared during verification") from exc
