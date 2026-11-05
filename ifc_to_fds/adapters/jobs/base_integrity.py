"""Adapter-side, fail-closed integrity verifier for a reusable scenario base.

No runtime scientific verdict is promoted here: this only checks the existing
persisted conversion result, its provenance index and the mapping checkpoint.
"""

from pathlib import Path

from ifc_to_fds.adapters.jobs.evidence_index import (
    EVIDENCE_FILENAME,
    _read_object,
    verify_evidence_index,
)
from ifc_to_fds.adapters.jobs.result_contract import validate_job_result


_REQUIRED_SEALED_FILES = frozenset({
    "result.json",
    "model.fds",
    "model_manifest.json",
    "model_acceptance_report.json",
    "model_geometry.json",
    "audit-state.json",
})


def verify_accepted_mapping_base(directory: Path) -> None:
    """Reject incomplete or modified base evidence before EV composition.

    An intact SHA-256 index proves disk consistency only, not independent CFD
    science, identity of the author, or a digital signature.
    """
    directory = Path(directory)
    result = _read_object(directory / "result.json")
    validate_job_result("convert", result)
    if (
        result.get("mapping_status") != "MAPPING_VERIFIED"
        or result.get("output_complete") is not True
    ):
        raise ValueError("Scenario base requires a completed verified mapping")
    verify_evidence_index(directory, "convert", result)

    index = _read_object(directory / EVIDENCE_FILENAME)
    files = index.get("files")
    if not isinstance(files, dict) or not _REQUIRED_SEALED_FILES.issubset(files):
        raise ValueError("Scenario base is missing indexed sealed mapping evidence")

    checkpoint = _read_object(directory / "audit-state.json")
    manifest = _read_object(directory / "model_manifest.json")
    if (
        checkpoint.get("status") != "MAPPING_VERIFIED"
        or checkpoint.get("checkpoint_status") != "VERIFIED_SEALED"
        or checkpoint.get("output_complete") is not True
        or checkpoint.get("bundle_sha256") != manifest.get("bundle_sha256")
    ):
        raise ValueError("Scenario base checkpoint is not verified and sealed")
