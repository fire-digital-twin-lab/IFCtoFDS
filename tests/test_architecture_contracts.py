"""Automated architecture tests verifying Hexagonal Architecture contracts."""

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Set

import pytest

ROOT_DIR = Path(__file__).parent.parent / "ifc_to_fds"


def get_imported_modules(py_file: Path) -> Set[str]:
    """Parse python source using AST and collect all fully-qualified imported module names."""
    content = py_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(py_file))
    imported = set()

    rel_path = py_file.relative_to(ROOT_DIR.parent)
    pkg_parts = rel_path.parent.parts

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base_len = len(pkg_parts) - (node.level - 1)
                base = list(pkg_parts[:max(0, base_len)])
                if node.module:
                    base.extend(node.module.split("."))
                module_name = ".".join(base)
                imported.add(module_name)
                for alias in node.names:
                    imported.add(f"{module_name}.{alias.name}")
            else:
                if node.module:
                    imported.add(node.module)
                    for alias in node.names:
                        imported.add(f"{node.module}.{alias.name}")
    return imported


def find_python_files(directory: Path) -> List[Path]:
    if not directory.is_dir():
        return []
    return list(directory.rglob("*.py"))


def test_domain_has_no_external_infrastructure_dependencies():
    """Domain layer must not import frameworks, I/O libraries, adapters, or outer layers."""
    domain_dir = ROOT_DIR / "domain"
    forbidden_prefixes = (
        "ifcopenshell",
        "fastapi",
        "uvicorn",
        "starlette",
        "subprocess",
        "requests",
        "httpx",
        "ifc_to_fds.adapters",
        "ifc_to_fds.interfaces",
        "ifc_to_fds.application",
        "ifc_to_fds.geometry",
        "ifc_to_fds.mapping",
        "ifc_to_fds.validation",
        "ifc_to_fds.pipeline",
        "ifc_to_fds.jobs",
        "ifc_to_fds.server",
        "ifc_to_fds.cli",
    )

    for py_file in find_python_files(domain_dir):
        imports = get_imported_modules(py_file)
        violations = {
            imp
            for imp in imports
            if any(imp == f or imp.startswith(f + ".") for f in forbidden_prefixes)
        }
        assert (
            not violations
        ), f"Architectural violation in {py_file}: Domain cannot import {violations}"


def test_domain_layer_does_not_import_validation():
    """Domain layer must not import from the outer validation package."""
    domain_dir = ROOT_DIR / "domain"
    for py_file in find_python_files(domain_dir):
        imports = get_imported_modules(py_file)
        violations = {
            imp
            for imp in imports
            if imp == "ifc_to_fds.validation" or imp.startswith("ifc_to_fds.validation.")
        }
        assert not violations, f"Layer boundary violation in {py_file}: Domain cannot import {violations}"


def test_application_has_no_concrete_adapter_or_framework_dependencies():
    """Application layer must not directly import concrete delivery frameworks, adapters, or bootstrap."""
    app_dir = ROOT_DIR / "application"
    forbidden_prefixes = (
        "ifcopenshell",
        "fastapi",
        "uvicorn",
        "starlette",
        "ifc_to_fds.adapters",
        "ifc_to_fds.interfaces",
        "ifc_to_fds.bootstrap",
    )

    for py_file in find_python_files(app_dir):
        imports = get_imported_modules(py_file)
        violations = {
            imp
            for imp in imports
            if any(imp == f or imp.startswith(f + ".") for f in forbidden_prefixes)
        }
        assert (
            not violations
        ), f"Architectural violation in {py_file}: Application cannot import {violations}"


def test_container_and_skeleton_structure_exists():
    """Verify core hexagonal directories exist and can be loaded."""
    from ifc_to_fds.bootstrap import Container, create_container

    container = create_container()
    assert isinstance(container, Container)
    assert container.config is not None
    assert container.get_artifact_repository() is not None
    assert container.get_reference_repository() is not None
    assert container.get_save_artifacts_use_case() is not None
    assert container.get_audit_conversion_use_case() is not None
    assert container.get_convert_verified_use_case() is not None


def test_mapping_plan_decouples_mapping_from_serialization(box_model):
    """MappingPlan must be generated independently and synchronize emitted primitive IDs upon serialization."""
    from ifc_to_fds.domain.mapping import MappingPlan, MappingDecision, build_mapping_plan
    from ifc_to_fds.mapping.exporter import serialize_fds

    plan = build_mapping_plan(box_model)
    assert isinstance(plan, MappingPlan)
    assert len(plan.decisions) == len(box_model.elements)

    elem = box_model.elements[0]
    decision = plan.get_decision(elem.entity_key)
    assert isinstance(decision, MappingDecision)
    assert decision.strategy == elem.mapping_strategy
    assert decision.simulation_role == elem.simulation_role
    assert decision.boundary_treatment == elem.boundary_treatment

    # Before serialize_fds, primitive IDs in plan are empty
    assert len(decision.fds_primitive_ids) == 0
    serialize_fds(box_model, mapping_plan=plan)
    # Plans describe intent; emitted IDs belong to the serialization result.
    assert decision.fds_primitive_ids == []
    assert len(elem.fds_primitive_ids) > 0


def test_artifact_repository_port_and_adapter(box_model, tmp_path):
    """ArtifactRepositoryPort is implemented by LocalFilesystemArtifactRepository."""
    from ifc_to_fds.adapters.storage.filesystem import LocalFilesystemArtifactRepository
    from ifc_to_fds.application.ports.storage import ArtifactRepositoryPort
    from ifc_to_fds.geometry.storage import write_package
    from ifc_to_fds.mapping.manifest import build_manifest

    repo = LocalFilesystemArtifactRepository()
    assert isinstance(repo, ArtifactRepositoryPort)
    manifest = build_manifest(box_model, fds_text="&OBST XB=0,2,0,1,0,3 /")
    dummy_result = {
        "fds_text": "&HEAD TITLE='test' /\n&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n&OBST XB=0,2,0,1,0,3 /",
        "manifest": manifest.model_dump(mode="json"),
        "report": {"status": "INCONCLUSIVE", "gates": {}},
        "inventory": {"elements": []},
        "mep_graph": {"systems": [], "connections": []},
        "configuration": {},
        "timings": {},
        "parity_report": {},
        "markdown_report": "# Test Report",
        "geometry_package": write_package(box_model, tmp_path / "pkg.json"),
    }
    checksums = repo.save_run_artifacts(dummy_result, tmp_path / "model.fds")
    assert isinstance(checksums, dict)
    assert len(checksums) > 0


def test_gate_checker_protocol_conformance(box_model):
    """All concrete gate checkers conform to GateChecker protocol and use context.parsed."""
    from ifc_to_fds.domain.validation.checkers.base import GateChecker
    from ifc_to_fds.validation.checkers import (
        AirPathTopologyChecker,
        BoundaryChecker,
        MeshResolutionChecker,
        ScopeChecker,
        SolverChecker,
        StructuralCompletenessChecker,
    )
    from ifc_to_fds.validation.checkers.hvac import HvacNetworkChecker

    checkers = [
        ScopeChecker(),
        StructuralCompletenessChecker(),
        AirPathTopologyChecker(),
        BoundaryChecker(),
        MeshResolutionChecker(),
        HvacNetworkChecker(),
        SolverChecker(),
    ]

    for checker in checkers:
        assert isinstance(checker, GateChecker), f"{checker.__class__.__name__} must conform to GateChecker protocol"
        assert hasattr(checker, "name")
        assert callable(getattr(checker, "check"))


def test_validation_engine_runs_and_reports_core_gates(box_model):
    """The single production validation path returns an evaluated AcceptanceReport."""
    from ifc_to_fds.validation.engine import run_independent_validation
    from ifc_to_fds.mapping.exporter import serialize_fds
    from ifc_to_fds.mapping.manifest import build_manifest
    from ifc_to_fds.domain.validation.model import AcceptanceReport, GateStatus

    fds_text, _ = serialize_fds(box_model)
    manifest = build_manifest(box_model, fds_text)
    report = run_independent_validation(box_model, fds_text, manifest)

    assert isinstance(report, AcceptanceReport)
    assert "syntax" in report.gates
    assert "domain" in report.gates
    assert "traceability" in report.gates
    assert "scope" in report.gates
    assert report.gates["syntax"].status == GateStatus.PASS
    assert report.gates["scope"].status == GateStatus.PASS
    assert report.gates["traceability"].status == GateStatus.PASS


def test_no_duplicate_job_repository_classes():
    """Exactly one JobRepository class may exist under ifc_to_fds/ (no shadow copies)."""
    found = []
    for py_file in find_python_files(ROOT_DIR):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        found += [
            str(py_file.relative_to(ROOT_DIR))
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "JobRepository"
        ]
    assert len(found) == 1, f"Expected one JobRepository class, found: {found}"


_COLD_IMPORT_MODULES = sorted(
    {f"ifc_to_fds.{d.name}" for d in ROOT_DIR.iterdir() if (d / "__init__.py").is_file()}
    | {
        "ifc_to_fds.fire",
        "ifc_to_fds.validation.engine",
        "ifc_to_fds.validation.checkers",
        "ifc_to_fds.validation.checkers.mesh_resolution",
        "ifc_to_fds.mapping",
        "ifc_to_fds.mep",
        "ifc_to_fds.server",
        "ifc_to_fds.adapters.jobs.runner",
    }
)


@pytest.mark.parametrize("module", _COLD_IMPORT_MODULES)
def test_module_imports_first_in_a_fresh_process(module):
    """Importing a module FIRST in a clean interpreter exposes circular imports."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "IFCFDS_SOLVER_AUTODISCOVERY": "0"},
    )
    assert result.returncode == 0, f"cold import of {module} failed:\n{result.stderr[-2000:]}"
