"""Automated architecture tests verifying Hexagonal Architecture contracts."""

import ast
from pathlib import Path
from typing import List, Set

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


def test_validation_evaluator_produces_immutable_report(box_model):
    """AcceptanceEvaluator constructs an AcceptanceReport with unexecuted gates defaulting to NOT_RUN."""
    from ifc_to_fds.domain.validation.evaluator import AcceptanceEvaluator
    from ifc_to_fds.domain.validation.checkers.base import CheckerOutcome
    from ifc_to_fds.domain.validation.model import (
        ValidationContext,
        GateResult,
        GateStatus,
        Finding,
        Severity,
        AuditConfig,
    )

    context = ValidationContext(
        model=box_model,
        fds_text="&HEAD TITLE='test' /\n&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n&OBST XB=0,2,0,1,0,3 /",
        manifest=None,
        config=AuditConfig(),
    )
    outcome = CheckerOutcome(
        gate_name="geometry",
        result=GateResult(status=GateStatus.PASS, reason="All solids verified"),
        findings=[
            Finding(
                id="FND-0001",
                severity=Severity.P2,
                category="geometry",
                title="Minor tolerance check",
                detail="Surface within tolerance",
                element_id="fixture:1",
            )
        ],
        element_statuses={"fixture:1": "MATCHED"},
    )
    evaluator = AcceptanceEvaluator()
    report = evaluator.evaluate(context, [outcome])
    assert report.total_elements_checked == 1
    assert report.matched_count == 1
    assert report.gates["geometry"].status == GateStatus.PASS
    # Unexecuted gates must be NOT_RUN (fail-safe principle)
    assert report.gates["syntax"].status == GateStatus.NOT_RUN
    assert report.gates["mep"].status == GateStatus.NOT_RUN
    assert report.gates["source_inventory"].status == GateStatus.NOT_RUN
    assert len(report.findings) == 1
    assert report.findings[0].id == "FND-0001"


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
    """Concrete gate checkers conform to GateChecker protocol and use context.parsed."""
    from ifc_to_fds.domain.validation.checkers.base import GateChecker
    from ifc_to_fds.domain.validation.model import ValidationContext, AuditConfig
    from ifc_to_fds.validation.checkers.syntax import FdsSyntaxChecker
    from ifc_to_fds.validation.checkers.domain import DomainChecker

    syntax_checker = FdsSyntaxChecker()
    assert isinstance(syntax_checker, GateChecker)

    domain_checker = DomainChecker()
    assert isinstance(domain_checker, GateChecker)

    context = ValidationContext(
        model=box_model,
        fds_text="&HEAD TITLE='test' /\n&MESH IJK=10,10,10, XB=0,2,0,1,0,3 /\n&OBST XB=0,2,0,1,0,3 /",
        manifest=None,
        config=AuditConfig(),
    )
    # Check that context.parsed lazily parses FDS text
    assert context.parsed is not None
    assert len(context.parsed.records) > 0

    syntax_outcome = syntax_checker.check(context)
    assert syntax_outcome.gate_name == "syntax"

    domain_outcome = domain_checker.check(context)
    assert domain_outcome.gate_name == "domain"
