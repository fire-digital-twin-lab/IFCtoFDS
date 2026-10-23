"""Public, bounded result metadata and registered research-source discovery."""

import json
import os
from pathlib import Path


def registered_cases():
    result = []
    from ifc_to_fds.modules.reference.api import FilesystemReferenceRepository
    repo = FilesystemReferenceRepository()
    for key, value in json.loads(
        os.environ.get("IFCFDS_REFERENCE_CASES", "{}")
    ).items():
        path = Path(value if isinstance(value, str) else value["path"])
        try:
            sources = json.loads((path / "sources.json").read_text(encoding="utf-8"))[
                "sources"
            ]
            approval = json.loads((path / "approval.json").read_text(encoding="utf-8"))
            try:
                checksum = repo.bundle_digest(path)
                if approval.get("bundle_sha256") == checksum:
                    integrity_status = "VERIFIED"
                    approval_status = approval.get("status", "DRAFT")
                else:
                    integrity_status = "CORRUPTED"
                    approval_status = "UNVERIFIED_CORRUPT"
            except Exception:
                integrity_status = "CORRUPTED"
                approval_status = "UNVERIFIED_CORRUPT"

            result.append(
                dict(
                    id=key,
                    name=value.get("name", key) if isinstance(value, dict) else key,
                    source_hashes=[s["file_hash_sha256"] for s in sources],
                    approval_status=approval_status,
                    integrity_status=integrity_status,
                )
            )
        except (OSError, ValueError, KeyError):
            result.append(
                dict(id=key, name=key, source_hashes=[], approval_status="UNAVAILABLE", integrity_status="UNAVAILABLE")
            )
    return result


def research_context(sources, config, report=None, *, cases=None):
    hashes = {s["file_hash_sha256"] for s in sources}
    matches = []
    for case in registered_cases() if cases is None else cases:
        expected = set(case["source_hashes"])
        if hashes & expected:
            matches.append(
                {**case, "source_match": "EXACT" if hashes == expected else "PARTIAL"}
            )
    gate = (report or {}).get("gates", {}).get("golden_reference_parity", {})
    return dict(
        known_cases=matches,
        profile=config.get("profile", "mapping"),
        parity_status=gate.get("status", "NOT_RUN")
        if config.get("reference_case")
        else "NOT_RUN",
        research_acceptance=(report or {}).get("mapping_status", "INCONCLUSIVE")
        if config.get("profile") == "research-basement"
        else "NOT_RUN",
    )

