"""Approved, content-bound reference cases; candidates never approve themselves."""

import copy
import json
from pathlib import Path
from ifc_to_fds.core.canonical import SCHEMA_VERSION, TriangleMesh
from ifc_to_fds.geometry.package import digest, verify_package, metrics_pass
from ifc_to_fds.mapping.manifest import MappingManifest
from .metrics import compare_solids
from .acceptance import GateResult, GateStatus, Finding, Severity

FIELDS = (
    "system_ids",
    "ports",
    "openings",
    "classification_evidence",
    "source_id",
    "global_id",
    "step_id",
    "ifc_type",
    "name",
    "type_class",
    "building_id",
    "scope_decision",
    "simulation_role",
    "operational_status",
    "fds_representation",
    "review_status",
    "boundary_treatment",
    "decision",
)
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
    "mep-reference.json",
    "acceptance-profile.json",
    "review-queue.json",
)


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted(
            (normalize(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True)
        )
    return value


def source_signature(sources):
    return normalize(
        [
            {
                k: s[k]
                for k in (
                    "source_id",
                    "file_hash_sha256",
                    "schema_version",
                    "unit_scale_to_meters",
                    "world_transform",
                )
            }
            for s in sources
        ]
    )


def snapshot(manifest):
    return {
        r.entity_key: {field: getattr(r, field) for field in FIELDS}
        for r in manifest.records
    }


def bundle_digest(directory):
    return digest(
        {
            name: json.loads((Path(directory) / name).read_text(encoding="utf-8"))
            for name in FILES
        }
    )


def resolve_case(case):
    # Server converts registered IDs to paths; local CLI also accepts paths.
    return Path(case)


def resolve_sources(case, mapping):
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


def create_candidate(directory, model, manifest, package, report, configuration):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(
            "Reference output must be a new empty directory; existing baseline is immutable"
        )
    directory.mkdir(parents=True, exist_ok=True)
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
    for name, value in values.items():
        (directory / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    checksum = bundle_digest(directory)
    (directory / "approval.json").write_text(
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
    (directory / "intentional-deltas.json").write_text(
        json.dumps(
            dict(status="DRAFT", reference_digest=checksum, changes=[]), indent=2
        ),
        encoding="utf-8",
    )
    return checksum


def inspect_case(directory):
    directory = Path(directory)
    approval = json.loads((directory / "approval.json").read_text(encoding="utf-8"))
    actual = bundle_digest(directory)
    if approval.get("bundle_sha256") != actual:
        raise ValueError("Reference bundle changed after its recorded revision")
    values = {
        name: json.loads((directory / name).read_text(encoding="utf-8"))
        for name in FILES
    }
    if values["acceptance-profile.json"].get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported reference schema")
    verify_package(values["geometry-package.json"])
    inventory = values["expected-inventory.json"]
    if inventory != snapshot(
        MappingManifest.model_validate(values["golden-manifest.json"])
    ):
        raise ValueError("Reference inventory conflicts with golden manifest")
    for name in (
        "structural-reference.json",
        "hvac-reference.json",
        "fire-protection-reference.json",
        "exclusions.json",
        "boundary-elements.json",
    ):
        if any(
            k not in inventory or v != inventory[k] for k, v in values[name].items()
        ):
            raise ValueError(f"Reference projection conflicts: {name}")
    return actual, approval, values


def golden_gate(report, model, manifest, package, configuration):
    profile = configuration.get("profile", "mapping")
    case = configuration.get("reference_case")
    gate = GateResult(status=GateStatus.PASS, required=True)
    report.gates["golden_reference_parity"] = gate

    def fail(key, field, expected, actual):
        gate.status = GateStatus.FAIL
        report.findings.append(
            Finding(
                id=f"GOLD-{len(report.findings)}",
                severity=Severity.P1,
                category="golden_reference_parity",
                title=f"Golden difference: {field}",
                element_id=key,
                detail=f"{field}: expected={expected!r}; actual={actual!r}",
                remediation="Review evidence or supply an explicitly approved delta",
            )
        )

    def unknown(reason):
        if gate.status != GateStatus.FAIL:
            gate.status = GateStatus.INCONCLUSIVE
        gate.reason += reason + "; "

    if not case:
        gate.status = (
            GateStatus.INCONCLUSIVE
            if profile == "research-basement"
            else GateStatus.NOT_APPLICABLE
        )
        gate.reason = (
            "Required research reference missing"
            if profile == "research-basement"
            else "No reference selected for general mapping"
        )
        return
    try:
        checksum, approval, values = inspect_case(case)
    except FileNotFoundError:
        unknown("Reference files unavailable")
        return
    except (ValueError, TypeError, KeyError) as exc:
        fail("", "reference_integrity", "valid reference", str(exc))
        return
    gate.evidence = dict(reference_sha256=checksum, reference_case=str(case))
    approved = approval.get("status") == "APPROVED" and all(
        approval.get(k) for k in ("reviewer", "rationale", "evidence")
    )
    if not approved:
        unknown("Reference is DRAFT or lacks human approval evidence")
        return
    expected = copy.deepcopy(values["expected-inventory.json"])
    reference_package = copy.deepcopy(values["geometry-package.json"])
    delta = configuration.get("intentional_deltas")
    if delta:
        if (
            not isinstance(delta, dict)
            or delta.get("reference_digest") != checksum
            or delta.get("status") != "APPROVED"
        ):
            fail("", "delta", "approved delta for this baseline", delta)
            return
        for change in delta.get("changes", []):
            key, field = change.get("entity_key"), change.get("field")
            if (
                key not in expected
                or field not in (*FIELDS, "geometry")
                or not all(change.get(k) for k in ("rationale", "reviewer", "evidence"))
            ):
                fail(
                    key or "",
                    "delta",
                    "explicit supported entity/field approval",
                    change,
                )
                continue
            target = (
                reference_package["elements"][key]
                if field == "geometry"
                else expected[key]
            )
            field_key = "mesh" if field == "geometry" else field
            if target.get(field_key) != change.get("before"):
                fail(key, "delta.before", target.get(field_key), change.get("before"))
                continue
            target[field_key] = change.get("after")
    actual = snapshot(manifest)
    for key in sorted(set(expected) | set(actual)):
        if key not in actual or key not in expected:
            fail(key, "inventory", key in expected, key in actual)
            continue
        for field in FIELDS:
            if normalize(expected[key].get(field)) != normalize(actual[key].get(field)):
                fail(key, field, expected[key].get(field), actual[key].get(field))
    if source_signature(values["sources.json"]["sources"]) != source_signature(
        manifest.sources
    ):
        fail(
            "",
            "sources",
            source_signature(values["sources.json"]["sources"]),
            source_signature(manifest.sources),
        )
    if values["scope.json"] != dict(
        scope=model.requested_scope, simulation_domain=manifest.simulation_domain
    ):
        fail(
            "",
            "scope/domain",
            values["scope.json"],
            dict(
                scope=model.requested_scope,
                simulation_domain=manifest.simulation_domain,
            ),
        )
    audit_settings = configuration.get("audit", {})
    baseline_settings = (
        values["acceptance-profile.json"].get("configuration", {}).get("audit", {})
    )
    for name, default in (
        ("surface_tolerance_m", 0.001),
        ("relative_volume_tolerance", 0.001),
        ("min_solid_iou", 0.999),
    ):
        if audit_settings.get(name, default) != baseline_settings.get(name, default):
            fail(
                "",
                "tolerance:" + name,
                baseline_settings.get(name, default),
                audit_settings.get(name, default),
            )
    saved_graph = configuration.get("mep_graph")
    if normalize(values["mep-reference.json"]) != normalize(saved_graph):
        # Report endpoint identities for missing/changed network records.
        wanted = {
            x["connection_id"]: x
            for x in values["mep-reference.json"].get("connections", [])
        }
        present = {
            x["connection_id"]: x for x in (saved_graph or {}).get("connections", [])
        }
        for key in sorted(set(wanted) | set(present)):
            if wanted.get(key) != present.get(key):
                edge = wanted.get(key) or present[key]
                fail(
                    edge.get("source_element_id", ""),
                    "connection:" + key,
                    wanted.get(key),
                    present.get(key),
                )
        if wanted == present:
            fail("", "MEP graph", values["mep-reference.json"], saved_graph)
    if package is None:
        unknown("Saved geometry package missing")
        return
    try:
        verify_package(package)
    except (ValueError, TypeError) as exc:
        fail("", "geometry_package", "valid checksum", str(exc))
        return
    for key in sorted(set(reference_package["elements"]) | set(package["elements"])):
        if key not in reference_package["elements"] or key not in package["elements"]:
            fail(
                key,
                "geometry_inventory",
                key in reference_package["elements"],
                key in package["elements"],
            )
        elif normalize(
            reference_package["elements"][key].get("ports", [])
        ) != normalize(package["elements"][key].get("ports", [])):
            fail(
                key,
                "ports",
                reference_package["elements"][key].get("ports"),
                package["elements"][key].get("ports"),
            )
    from .acceptance import AuditConfig

    config = AuditConfig.model_validate(audit_settings)
    for key, entry in reference_package["elements"].items():
        source = entry.get("mesh")
        saved = package["elements"].get(key, {}).get("mesh")
        if source is None and saved is None:
            continue
        if source is None or saved is None:
            fail(key, "preserved_geometry", bool(source), bool(saved))
            continue
        try:
            metrics = compare_solids(
                TriangleMesh.model_validate(source),
                [TriangleMesh.model_validate(saved)],
            )
            gate.evidence.setdefault("geometry_metrics", {})[key] = metrics
            if not metrics_pass(metrics, config):
                fail(key, "preserved_geometry", "within tolerances", metrics)
            elif not metrics["surface_proven"]:
                unknown(f"Full surface proof missing: {key}")
        except ValueError as exc:
            fail(key, "preserved_geometry", "valid solid", str(exc))
        except Exception as exc:
            unknown(f"Geometry comparison unavailable for {key}: {exc}")
    for key, entry in reference_package["elements"].items():
        actual_openings = package["elements"].get(key, {}).get("openings", {})
        if set(entry.get("openings", {})) != set(actual_openings):
            fail(
                key,
                "opening_inventory",
                list(entry.get("openings", {})),
                list(actual_openings),
            )
        for opening_id, source in entry.get("openings", {}).items():
            output = actual_openings.get(opening_id)
            if source is None or output is None:
                unknown(f"Opening geometry missing: {key}/{opening_id}")
                continue
            try:
                measured = compare_solids(
                    TriangleMesh.model_validate(source),
                    [TriangleMesh.model_validate(output)],
                )
                if not metrics_pass(measured, config):
                    fail(key, "opening_geometry:" + opening_id, "equivalent", measured)
                elif not measured["surface_proven"]:
                    unknown(f"Opening full surface proof missing: {key}/{opening_id}")
            except ValueError as exc:
                fail(key, "opening_geometry:" + opening_id, "valid solid", str(exc))
            except Exception as exc:
                unknown(f"Opening comparison unavailable: {key}/{opening_id}: {exc}")
    # Actual FDS geometry/opening findings are propagated to this gate. IDs and
    # checksums alone can never establish parity with a golden solid.
    for finding in list(report.findings):
        if finding.category in (
            "geometry",
            "openings",
            "representation",
            "scope",
            "domain",
            "geometry_preservation",
            "traceability",
            "source_inventory",
            "mep",
        ):
            fail(
                finding.element_id,
                f"actual_output:{finding.category}",
                "equivalent geometry/role",
                finding.detail,
            )
    for name, result in list(report.gates.items()):
        if (
            name != "golden_reference_parity"
            and result.required
            and result.status == GateStatus.FAIL
        ):
            fail("", "actual_gate:" + name, "PASS", result.reason)
    for name in ("geometry", "openings", "geometry_preservation", "boundary"):
        if report.gates.get(name) and report.gates[name].status in (
            GateStatus.NOT_RUN,
            GateStatus.INCONCLUSIVE,
        ):
            unknown(f"Required actual-output evidence incomplete: {name}")
    for alias in values["alias-decisions.json"]:
        key, target = alias.get("entity_key"), alias.get("geometry_entity_key")
        if not all(alias.get(k) for k in ("reviewer", "rationale", "evidence")):
            unknown(f"Alias approval evidence missing: {key}")
            continue
        try:
            import numpy as np

            matrix = np.asarray(alias.get("transform", np.eye(4)), dtype=float).reshape(
                4, 4
            )
            if (
                not np.isfinite(matrix).all()
                or not np.allclose(matrix[3], [0, 0, 0, 1])
                or not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3))
                or np.linalg.det(matrix[:3, :3]) < 0
            ):
                raise ValueError("Alias transform must be rigid")
            original = TriangleMesh.model_validate(package["elements"][key]["mesh"])
            reused = TriangleMesh.model_validate(package["elements"][target]["mesh"])
            reused.vertices = (
                np.asarray(reused.vertices) @ matrix[:3, :3].T + matrix[:3, 3]
            ).tolist()
            measured = compare_solids(original, [reused])
            if not metrics_pass(measured, config):
                fail(key, "alias_geometry", "equivalent", measured)
            elif not measured["surface_proven"]:
                unknown(f"Alias full surface proof incomplete: {key}")
        except (ValueError, KeyError, TypeError) as exc:
            fail(key or "", "alias_geometry", "valid equivalent solid", str(exc))
        except Exception as exc:
            unknown(f"Alias measurement unavailable: {key}: {exc}")
