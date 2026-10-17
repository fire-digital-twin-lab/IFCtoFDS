"""Filesystem implementation of ReferenceRepository port."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from ifc_to_fds.geometry.package import digest

FILES = (
    "sources.json",
    "scope.json",
    "expected-inventory.json",
    "structural-reference.json",
    "openings-reference.json",
    "hvac-reference.json",
    "fire-protection-reference.json",
    "exclusions.json",
    "boundary-elements.json",
    "alias-decisions.json",
    "golden-manifest.json",
    "golden-geometry-metrics.json",
    "geometry-package.json",
    "fds-geometry.json",
    "mep-reference.json",
    "acceptance-profile.json",
    "review-queue.json",
)


class FilesystemReferenceRepository:
    """Manages on-disk golden reference cases, signatures, and candidates."""

    def bundle_digest(self, directory: Path | str) -> str:
        return digest(
            {
                name: json.loads((Path(directory) / name).read_text(encoding="utf-8"))
                for name in FILES
            }
        )

    def inspect_case(self, directory: Path | str) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        path = Path(directory)
        approval = json.loads((path / "approval.json").read_text(encoding="utf-8"))
        files = {f: json.loads((path / f).read_text(encoding="utf-8")) for f in FILES}
        checksum = digest(files)
        if approval.get("bundle_sha256") != checksum:
            raise ValueError("Reference bundle changed after its recorded revision")
        if approval.get("status") not in ("DRAFT", "APPROVED", "SUPERSEDED"):
            raise ValueError("Invalid reference approval status")
        from ifc_to_fds.geometry.storage import read_package
        from ifc_to_fds.validation.reference_integrity import validate_reference

        files["geometry-package.json"] = read_package(path / "geometry-package.json")
        validate_reference(files)
        return checksum, approval, files

    def resolve_sources(self, case: Path | str, mapping: Dict[str, str]) -> List[Path]:
        spec = json.loads((Path(case) / "sources.json").read_text(encoding="utf-8"))
        result = []
        import hashlib

        for item in spec["sources"]:
            path = Path(mapping.get(item["source_id"], ""))
            if not path.is_file():
                raise ValueError(f"EXTERNAL_FIXTURE_NOT_AVAILABLE: {item['source_id']}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["file_hash_sha256"]:
                raise ValueError(f"External fixture checksum mismatch: {path.name}")
            result.append(path)
        return result

    def save_candidate_bundle(self, directory: Path | str, values: Dict[str, Any]) -> None:
        directory = Path(directory)
        if directory.exists() and any(directory.iterdir()):
            raise ValueError(
                "Reference output must be a new empty directory; existing baseline is immutable"
            )
        directory.mkdir(parents=True, exist_ok=True)
        for name, payload in values.items():
            (directory / name).write_text(
                json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
            )
