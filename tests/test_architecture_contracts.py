"""Automated architecture tests verifying Hexagonal Architecture contracts."""

import ast
from pathlib import Path
from typing import List, Set

ROOT_DIR = Path(__file__).parent.parent / "ifc_to_fds"


def get_imported_modules(py_file: Path) -> Set[str]:
    """Parse python source using AST and collect all imported module top-level names."""
    content = py_file.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(py_file))
    imported = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
            elif node.level and node.level > 0:
                pass  # relative import within package
    return imported


def find_python_files(directory: Path) -> List[Path]:
    if not directory.is_dir():
        return []
    return list(directory.rglob("*.py"))


def test_domain_has_no_external_infrastructure_dependencies():
    """Domain layer must not import frameworks, I/O libraries, or adapters."""
    domain_dir = ROOT_DIR / "domain"
    forbidden = {
        "ifcopenshell",
        "fastapi",
        "uvicorn",
        "subprocess",
        "requests",
        "httpx",
        "adapters",
        "interfaces",
    }

    for py_file in find_python_files(domain_dir):
        imports = get_imported_modules(py_file)
        violations = imports.intersection(forbidden)
        assert (
            not violations
        ), f"Architectural violation in {py_file}: Domain cannot import {violations}"


def test_application_has_no_concrete_adapter_or_framework_dependencies():
    """Application layer must not directly import concrete delivery frameworks or external libraries."""
    app_dir = ROOT_DIR / "application"
    forbidden = {
        "ifcopenshell",
        "fastapi",
        "uvicorn",
        "adapters",
        "interfaces",
    }

    for py_file in find_python_files(app_dir):
        imports = get_imported_modules(py_file)
        violations = imports.intersection(forbidden)
        assert (
            not violations
        ), f"Architectural violation in {py_file}: Application cannot import {violations}"


def test_container_and_skeleton_structure_exists():
    """Verify core hexagonal directories exist and can be loaded."""
    from ifc_to_fds.bootstrap import Container, create_container

    container = create_container()
    assert isinstance(container, Container)
    assert container.config is not None
