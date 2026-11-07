"""Resolve an accepted artifact bundle; never synthesize a replacement building."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Callable

from ifc_to_fds.domain.bim import BoundingBox
from ifc_to_fds.domain.mapping import MappingDecision, MappingManifest, MappingPlan
from ifc_to_fds.domain.validation import AcceptanceReport
from ifc_to_fds.geometry.mesh import valid_solid
from ifc_to_fds.geometry.package import verify_package
from ifc_to_fds.geometry.storage import DiskPackage
from ifc_to_fds.fire.base_geometry import VerifiedBaseGeometry
from ifc_to_fds.validation.parser import ParsedFDS, parse_fds


@dataclass(frozen=True)
class VerifiedScenarioBase:
    fds_text: str
    mapping_plan: MappingPlan
    manifest: MappingManifest
    emitted_geometry: VerifiedBaseGeometry


def _extract_verified_emitted_geometry(
    parsed: ParsedFDS,
    manifest: MappingManifest,
) -> VerifiedBaseGeometry:
    """Bind parsed GEOM meshes to sealed manifest identities without guessing."""

    records = {record.entity_key: record for record in manifest.records}
    expected_by_primitive: dict[str, str] = {}
    expected_ids_by_entity: dict[str, list[str]] = {}

    for record in manifest.records:
        if str(record.fds_representation).upper() != "GEOM":
            continue
        for primitive_id in record.fds_primitive_ids:
            if primitive_id in expected_by_primitive:
                raise ValueError(
                    f"Duplicate GEOM primitive identity in manifest: {primitive_id}"
                )
            expected_by_primitive[primitive_id] = record.entity_key
            expected_ids_by_entity.setdefault(record.entity_key, []).append(primitive_id)

    meshes: dict[str, list[TriangleMesh]] = {}
    seen: set[str] = set()
    for primitive in parsed.primitives:
        if primitive.kind != "GEOM":
            continue
        primitive_id = primitive.id
        expected_key = expected_by_primitive.get(primitive_id)
        if expected_key is None:
            raise ValueError(
                f"Verified base FDS contains untracked GEOM primitive: {primitive_id}"
            )
        source_key = str(primitive.source.get("entity_key", ""))
        if source_key != expected_key:
            raise ValueError(
                f"GEOM provenance differs from sealed manifest: {primitive_id}"
            )
        owners = manifest.primitive_to_ifc.get(primitive_id)
        if owners != [expected_key]:
            raise ValueError(
                f"GEOM reverse provenance differs from sealed manifest: {primitive_id}"
            )
        record = records.get(expected_key)
        if record is None or primitive_id not in record.fds_primitive_ids:
            raise ValueError(
                f"GEOM primitive is not owned by its manifest record: {primitive_id}"
            )
        mesh = primitive.mesh()
        if not valid_solid(mesh):
            raise ValueError(
                f"Verified base emitted GEOM is not a valid solid: {primitive_id}"
            )
        meshes.setdefault(expected_key, []).append(mesh)
        seen.add(primitive_id)

    if seen != set(expected_by_primitive):
        missing = sorted(set(expected_by_primitive) - seen)
        raise ValueError(f"Verified base FDS is missing sealed GEOM primitives: {missing}")

    return VerifiedBaseGeometry(
        geom_meshes={key: tuple(value) for key, value in meshes.items()},
        geom_primitive_ids={
            key: tuple(sorted(value))
            for key, value in expected_ids_by_entity.items()
        },
    )


def load_verified_scenario_base(
    job_root,
    bundle_sha,
    *,
    verify_candidate: Callable[[Path], None],
) -> VerifiedScenarioBase:
    """Load a sealed mapping plus exact emitted geometry for scenario checks."""

    if not callable(verify_candidate):
        raise ValueError("A persisted mapping evidence verifier is required")
    if (
        not isinstance(bundle_sha, str)
        or len(bundle_sha) != 64
        or any(c not in "0123456789abcdef" for c in bundle_sha)
    ):
        raise ValueError("A valid verified base bundle hash is required")

    for directory in sorted(Path(job_root).iterdir()):
        path = directory / "model_manifest.json"
        if not directory.is_dir() or not path.is_file():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("bundle_sha256") != bundle_sha:
            continue
        manifest = MappingManifest.model_validate(raw)
        if (
            manifest.compute_bundle_sha256() != bundle_sha
            or not manifest.output_complete
            or manifest.mapping_acceptance != "MAPPING_VERIFIED"
        ):
            raise ValueError("Base artifact is unsealed or not MAPPING_VERIFIED")

        verify_candidate(directory)
        report = AcceptanceReport.model_validate_json(
            (directory / "model_acceptance_report.json").read_text(encoding="utf-8")
        )
        if report.finalize().mapping_status.value != "MAPPING_VERIFIED":
            raise ValueError("Base acceptance report does not verify the mapping")

        text = (directory / "model.fds").read_bytes().decode("utf-8")
        if hashlib.sha256(text.encode()).hexdigest() != manifest.fds_sha256:
            raise ValueError("Base FDS hash differs from verified manifest")

        package = DiskPackage(directory / "model_geometry.json")
        verify_package(package)
        if package["sha256"] != manifest.geometry_package_sha256:
            raise ValueError("Base geometry package differs from verified manifest")

        parsed = parse_fds(text)
        if parsed.errors or parsed.unsupported:
            raise ValueError("Verified base FDS cannot be parsed with supported grammar")

        decisions = [
            MappingDecision(
                entity_key=record.entity_key,
                strategy=record.mapping_strategy,
                simulation_role=record.simulation_role,
                fds_representation=record.fds_representation,
                fds_primitive_ids=record.fds_primitive_ids,
                representation_bounds=record.representation_bounds,
                element_bounds=record.source_bounds,
                source_ifc_type=record.ifc_type,
                source_type_class=record.type_class,
                placement=record.placement,
                scope_decision=record.scope_decision,
                decision=record.decision,
                review_status=record.review_status,
            )
            for record in manifest.records
        ]
        plan = MappingPlan(
            decisions=decisions,
            simulation_domain=BoundingBox.model_validate(manifest.simulation_domain),
            cell_size=manifest.configuration.get("cell_size", 0.2),
        )
        geometry = _extract_verified_emitted_geometry(parsed, manifest)
        return VerifiedScenarioBase(
            fds_text=text,
            mapping_plan=plan,
            manifest=manifest,
            emitted_geometry=geometry,
        )

    raise ValueError(
        "Verified base bundle not found; convert and verify the building first"
    )


def load_verified_base(
    job_root,
    bundle_sha,
    *,
    verify_candidate: Callable[[Path], None],
):
    """Compatibility facade returning the historical three-value tuple."""

    base = load_verified_scenario_base(
        job_root,
        bundle_sha,
        verify_candidate=verify_candidate,
    )
    return base.fds_text, base.mapping_plan, base.manifest


__all__ = [
    "VerifiedBaseGeometry",
    "VerifiedScenarioBase",
    "load_verified_base",
    "load_verified_scenario_base",
]
