"""Golden reference parity evaluation gate."""

import copy
from pathlib import Path
from typing import Any, Dict, Optional
from ifc_to_fds.runtime.normalization import normalize
from ifc_to_fds.runtime.diagnostics import operation
from ifc_to_fds.domain.bim.model import TriangleMesh
from ifc_to_fds.domain.validation.model import AuditConfig, Finding, GateResult, GateStatus, Severity
from ifc_to_fds.modules.geometry.api import solid_boolean
from ifc_to_fds.modules.geometry.api import as_trimesh
from ifc_to_fds.modules.geometry.api import metrics_pass, verify_package
from ifc_to_fds.modules.reference.infrastructure.bundle_io import inspect_case
from ifc_to_fds.modules.reference.application.projections import serialized_geometry, source_signature
from ifc_to_fds.modules.geometry.api import compare_solids, passage_metrics
from ifc_to_fds.modules.reference.application.integrity import FIELDS, snapshot


@operation("GOLDEN")
def golden_gate(
    report: Any,
    model: Any,
    manifest: Any,
    package: Any,
    configuration: Dict[str, Any],
    fds_text: Optional[str] = None,
    *, case_reader=None,
) -> None:
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
        checksum, approval, values = (case_reader or inspect_case)(case)
    except FileNotFoundError:
        unknown("Reference files unavailable")
        return
    except (ValueError, TypeError, KeyError) as exc:
        fail("", "reference_integrity", "valid reference", str(exc))
        return
    approved = approval.get("status") == "APPROVED" and all(
        approval.get(k) for k in ("reviewer", "rationale", "evidence")
    )
    evidence: Dict[str, Any] = {
        "reference_sha256": checksum,
        "reference_case": Path(case).name,
        "data_integrity_verified": True,
        "human_approval_verified": bool(approved),
        "approval_status": approval.get("status", "DRAFT"),
        "reviewer": approval.get("reviewer"),
    }
    gate.evidence = evidence
    if not approved:
        unknown("Reference is DRAFT or lacks human approval evidence")
        return
    if values["acceptance-profile.json"].get("schema_version") == "0.4.0":
        unknown(
            "Legacy reference requires a new reviewed revision for placement and boundary contracts"
        )
        return
    expected = copy.deepcopy(values["expected-inventory.json"])
    reference_package = copy.deepcopy(values["geometry-package.json"])
    reference_fds = copy.deepcopy(values["fds-geometry.json"])
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
                or field not in (*FIELDS, "geometry", "fds_geometry")
                or not all(change.get(k) for k in ("rationale", "reviewer", "evidence"))
            ):
                fail(
                    key or "",
                    "delta",
                    "explicit supported entity/field approval",
                    change,
                )
                continue
            if field == "fds_geometry":
                current = reference_fds["entries"].get(key)
                if current != change.get("before"):
                    fail(key, "delta.before", current, change.get("before"))
                    continue
                after = change.get("after")
                if after is None:
                    reference_fds["entries"].pop(key, None)
                elif isinstance(after, list) and after:
                    try:
                        for mesh in after:
                            TriangleMesh.model_validate(mesh)
                        reference_fds["entries"][key] = after
                    except ValueError as exc:
                        fail(key, "delta.fds_geometry", "valid geometry", str(exc))
                else:
                    fail(key, "delta.fds_geometry", "mesh list or null", after)
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
            from ifc_to_fds.modules.geometry.api import DiskPackage

            if field == "geometry" and isinstance(reference_package, DiskPackage):
                reference_package.overrides[key] = target
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

    config = AuditConfig.model_validate(audit_settings)
    baseline_fds = reference_fds
    actual_fds = serialized_geometry(fds_text, manifest)
    if not baseline_fds.get("complete") or not actual_fds.get("complete"):
        unknown("Actual or reference FDS solid evidence missing/unsupported")
    else:
        expected_solids = baseline_fds["entries"]
        actual_solids = actual_fds["entries"]
        for key in sorted(set(expected_solids) | set(actual_solids)):
            if not expected_solids.get(key) or not actual_solids.get(key):
                fail(
                    key,
                    "fds_geometry_inventory",
                    bool(expected_solids.get(key)),
                    bool(actual_solids.get(key)),
                )
                continue
            try:
                pieces = [TriangleMesh.model_validate(m) for m in expected_solids[key]]
                if len(pieces) == 1:
                    reference = pieces[0]
                else:
                    union = solid_boolean([as_trimesh(m) for m in pieces], "union")
                    reference = TriangleMesh(
                        vertices=union.vertices.tolist(), faces=union.faces.tolist()
                    )
                measured = compare_solids(
                    reference,
                    [TriangleMesh.model_validate(m) for m in actual_solids[key]],
                )
                gate.evidence.setdefault("fds_geometry_metrics", {})[key] = measured
                if not metrics_pass(measured, config):
                    fail(
                        key,
                        "golden_fds_geometry",
                        "equivalent accepted FDS solid",
                        measured,
                    )
                elif not measured["surface_proven"]:
                    unknown(f"Golden FDS full surface proof missing: {key}")
            except ValueError as exc:
                fail(key, "golden_fds_geometry", "valid solid", str(exc))
            except Exception as exc:
                unknown(f"Golden FDS geometry unavailable: {key}: {exc}")
        reference_obstacles = [
            TriangleMesh.model_validate(m)
            for group in expected_solids.values()
            for m in group
        ]
        actual_obstacles = [
            TriangleMesh.model_validate(m)
            for group in actual_solids.values()
            for m in group
        ]
        for key, entry in reference_package["elements"].items():
            for opening_id, mesh in entry.get("openings", {}).items():
                if mesh is None:
                    unknown(f"Golden passage probe missing: {key}/{opening_id}")
                    continue
                try:
                    probe = TriangleMesh.model_validate(mesh)
                    passage = passage_metrics(
                        reference_obstacles, actual_obstacles, probe
                    )
                    solid = as_trimesh(probe)
                    tolerance = max(
                        1e-6,
                        config.surface_tolerance_m
                        * solid.area
                        / max(solid.volume, 1e-12),
                    )
                    if (
                        passage["normalized_symmetric_difference"] > tolerance
                        or passage["source_free_components"]
                        != passage["output_free_components"]
                    ):
                        fail(
                            key,
                            "golden_air_passage:" + opening_id,
                            "equivalent free volume",
                            passage,
                        )
                except Exception as exc:
                    unknown(
                        f"Golden passage comparison unavailable: {key}/{opening_id}: {exc}"
                    )
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
            unknown(f"Alias comparison failed: {key}: {exc}")
