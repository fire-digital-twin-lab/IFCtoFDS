"""Bundle I/O, checksum computation, and candidate creation for reference cases."""

import json
from pathlib import Path
from typing import Any, Dict
from ifc_to_fds.adapters.reference import FILES as FILES, FilesystemReferenceRepository
from ifc_to_fds.domain.version import SCHEMA_VERSION
from ifc_to_fds.geometry.storage import DiskPackage, copy_package
from ifc_to_fds.validation.golden.normalizer import serialized_geometry
from ifc_to_fds.validation.reference_integrity import snapshot

_repo = FilesystemReferenceRepository()


def bundle_digest(directory: str | Path) -> str:
    """Computes SHA-256 bundle digest over all reference JSON files."""
    return _repo.bundle_digest(directory)


def resolve_case(case: str | Path) -> Path:
    """Server converts registered IDs to paths; local CLI also accepts paths."""
    return Path(case)


def resolve_sources(case: str | Path, mapping: Any) -> Any:
    return _repo.resolve_sources(case, mapping)


def inspect_case(directory: str | Path) -> Any:
    """Compatibility entrypoint with the same integrity checks as the adapter."""
    return _repo.inspect_case(directory)


def create_candidate(
    directory: str | Path,
    model: Any,
    manifest: Any,
    package: Any,
    report: Any,
    configuration: Dict[str, Any],
    fds_text: str | None = None,
) -> str:
    """Generates a candidate reference bundle for human review."""
    dir_path = Path(directory)
    if dir_path.exists() and any(dir_path.iterdir()):
        raise ValueError(
            "Reference output must be a new empty directory; existing baseline is immutable"
        )
    dir_path.mkdir(parents=True, exist_ok=True)
    records = snapshot(manifest)
    selected = {e.entity_key: e for e in model.elements}

    def subset(predicate):
        return {k: v for k, v in records.items() if predicate(selected[k])}

    values = {
        "sources.json": dict(
            schema_version=SCHEMA_VERSION,
            sources=[
                s.model_dump(mode="json", exclude={"file_path"})
                for s in model.sources or [model.source]
            ],
        ),
        "scope.json": dict(
            scope=model.requested_scope, simulation_domain=manifest.simulation_domain
        ),
        "expected-inventory.json": records,
        "structural-reference.json": subset(
            lambda e: e.role == "PHYSICAL" and not e.classification_evidence
        ),
        "openings-reference.json": {
            e.entity_key: [
                dict(
                    step_id=o.opening_step_id,
                    global_id=o.opening_global_id,
                    fillings=o.filling_global_ids,
                )
                for o in e.openings
            ]
            for e in model.elements
            if e.openings
        },
        "hvac-reference.json": subset(
            lambda e: e.mep_category in ("VENTILATION", "SMOKE_EXTRACT")
        ),
        "fire-protection-reference.json": subset(
            lambda e: e.mep_category == "FIRE_SUPPRESSION"
        ),
        "exclusions.json": subset(
            lambda e: (
                e.mapping_strategy.value in ("EXCLUDED_SCOPE", "EXCLUDED_APPROVED")
            )
        ),
        "boundary-elements.json": subset(
            lambda e: (
                e.boundary_treatment == "PENDING_VALIDATION"
                or e.scope_decision.value == "BOUNDARY_RETAINED"
            )
        ),
        "alias-decisions.json": [],
        "golden-manifest.json": manifest.model_dump(mode="json"),
        "golden-geometry-metrics.json": report.metrics,
        "geometry-package.json": package,
        "fds-geometry.json": serialized_geometry(fds_text, manifest),
        "mep-reference.json": model.mep_graph.model_dump(mode="json"),
        "acceptance-profile.json": dict(
            schema_version=SCHEMA_VERSION,
            configuration=configuration,
            status="DRAFT",
            origin="AUTOMATIC_CANDIDATE_NOT_GROUND_TRUTH",
        ),
        "review-queue.json": [
            dict(
                entity_key=e.entity_key,
                review_status=e.review_status,
                boundary_treatment=e.boundary_treatment,
            )
            for e in model.elements
            if e.review_status == "REVIEW_REQUIRED"
            or e.boundary_treatment == "PENDING_VALIDATION"
        ],
    }

    if isinstance(package, DiskPackage):
        copy_package(package, dir_path / "geometry-package.json")
        values.pop("geometry-package.json")
    for name, value in values.items():
        (dir_path / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    checksum = bundle_digest(dir_path)
    (dir_path / "approval.json").write_text(
        json.dumps(
            dict(
                status="DRAFT",
                bundle_sha256=checksum,
                reviewer=None,
                rationale=None,
                evidence=[],
            ),
            indent=2,
        ),
        encoding="utf-8",
    )
    (dir_path / "intentional-deltas.json").write_text(
        json.dumps(
            dict(status="DRAFT", reference_digest=checksum, changes=[]), indent=2
        ),
        encoding="utf-8",
    )
    return checksum
