"""Build saved mapping evidence for cross-module regression tests."""

from ifc_to_fds.modules.fds.api import serialize_fds, build_manifest
from ifc_to_fds.modules.geometry.api import build_package, audit_package
from ifc_to_fds.modules.verification.api import run_independent_validation
from ifc_to_fds.modules.verification.contracts import AuditConfig


def checked(model, text=None, package=None, configuration=None):
    if text is None:
        text, _ = serialize_fds(model)
    package = build_package(model) if package is None else package
    config = configuration or {"mep_graph": model.mep_graph.model_dump(mode="json")}
    manifest = build_manifest(model, text, config)
    manifest.geometry_package_sha256 = package["sha256"]
    report = run_independent_validation(model, text, manifest)
    audit_package(model, package, report, AuditConfig())
    report.configuration["test_serialized_fds"] = text
    return text, manifest, package, report, config
