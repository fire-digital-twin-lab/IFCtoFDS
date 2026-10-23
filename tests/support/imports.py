"""Resolve absolute and relative Python imports for architecture checks."""

import ast
from pathlib import Path
from typing import Set

ROOT_DIR = Path(__file__).resolve().parents[2] / "ifc_to_fds"

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
