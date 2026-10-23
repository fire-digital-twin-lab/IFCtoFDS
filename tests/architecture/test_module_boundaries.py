"""Executable module boundaries and replacement contracts for the monolith."""

import ast
import importlib
from pathlib import Path

import pytest
from tests.support.imports import get_imported_modules

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "ifc_to_fds/modules"
OWNERS = {path.parent.name for path in MODULES.glob("*/api.py")}


def public_exports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return ast.literal_eval(next(
        node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_EXPORTS" for target in node.targets)
    ))


def test_module_callers_use_public_api_and_dependency_graph_has_no_cycles():
    graph = {owner: set() for owner in OWNERS}
    for path in (ROOT / "ifc_to_fds").rglob("*.py"):
        parts = path.relative_to(ROOT / "ifc_to_fds").parts
        owner = parts[1] if parts[0] == "modules" and len(parts) > 2 else None
        # Legacy import facades retain old surfaces; new implementation is checked.
        if parts[0] in {"geometry", "mapping", "validation", "mep", "core"}:
            continue
        for module in get_imported_modules(path):
            imported = module.split(".")
            if imported[:2] != ["ifc_to_fds", "modules"] or len(imported) < 3 or imported[2] not in OWNERS:
                continue
            target = imported[2]
            if target != owner:
                assert len(imported) > 3 and imported[3] in ("api", "contracts"), f"Private module access: {path}: {module}"
                if owner in graph and target in graph:
                    graph[owner].add(target)
    for owner in graph:
        for target, _ in public_exports(MODULES / owner / "api.py").values():
            parts = target.split(".")
            if parts[:2] == ["ifc_to_fds", "modules"] and parts[2] != owner:
                graph[owner].add(parts[2])

    def visit(node, ancestors):
        assert node not in ancestors, f"Module cycle: {' -> '.join([*ancestors, node])}"
        for target in graph[node]:
            visit(target, [*ancestors, node])

    for owner in graph:
        visit(owner, [])


def test_domain_does_not_import_modules_or_delivery():
    for path in (ROOT / "ifc_to_fds/domain").rglob("*.py"):
        for module in get_imported_modules(path):
            assert not module.startswith(("ifc_to_fds.modules", "ifc_to_fds.bootstrap", "ifc_to_fds.interfaces")), path


@pytest.mark.parametrize("owner", sorted(OWNERS))
def test_every_public_symbol_resolves(owner):
    module = importlib.import_module(f"ifc_to_fds.modules.{owner}.api")
    for name in module.__all__:
        assert getattr(module, name) is not None, f"{owner}.{name}"


@pytest.mark.parametrize("old,new", [
    ("core.inventory", "modules.bim.inventory"),
    ("core.federation", "modules.bim.federation"),
    ("geometry.mesh", "modules.geometry.mesh"),
    ("geometry.preview", "modules.bim.preview"),
    ("mapping.exporter", "modules.fds.serializer"),
    ("validation.parser", "modules.fds.parser"),
    ("validation.engine", "modules.verification.engine"),
    ("validation.metrics", "modules.geometry.metrics"),
    ("adapters.jobs.runner", "interfaces.worker.runner"),
])
def test_compatibility_modules_share_identity_for_monkeypatches_and_caches(old, new):
    assert importlib.import_module("ifc_to_fds." + old) is importlib.import_module("ifc_to_fds." + new)


def test_exporter_replacement_obeys_real_signature_and_preserves_intent(box_model):
    from ifc_to_fds.adapters.fds.exporter import FdsExporter
    from ifc_to_fds.application.ports.output.fds_exporter_port import FdsExporterPort
    from ifc_to_fds.domain.mapping import build_mapping_plan
    from ifc_to_fds.modules.fds.api import serialize_fds

    plan = build_mapping_plan(box_model, cell_size=0.5)
    before = plan.model_dump()
    adapter = FdsExporter()
    assert isinstance(adapter, FdsExporterPort)
    expected_text, expected_manifest = serialize_fds(box_model.model_copy(deep=True), cell_size=0.5, mapping_plan=plan)
    actual_text, actual_manifest = adapter.serialize_fds(box_model, cell_size=0.5, mapping_plan=plan)
    assert actual_text == expected_text
    assert actual_manifest.model_dump() == expected_manifest.model_dump()
    assert plan.model_dump() == before


def test_http_factory_does_not_open_job_repository_on_import_or_share_managers():
    from ifc_to_fds.interfaces.http.app import create_app

    first, second = create_app(), create_app()
    assert first.state.job_manager is not second.state.job_manager
    assert first.state.job_manager._instance is None
    assert second.state.job_manager._instance is None
    first.state.job_manager.close()
    assert first.state.job_manager._instance is None
    paths = set(first.openapi()["paths"])
    assert {"/", "/index.html", "/guide.html", "/api/health", "/api/jobs", "/api/preview-jobs"} <= paths


def test_frontend_entry_and_worker_assets_resolve():
    import re

    frontend = ROOT / "frontend"
    for name in ("index.html", "guide.html"):
        text = (frontend / name).read_text(encoding="utf-8")
        for src in re.findall(r'(?:src|href)="([^"#]+)"', text):
            if src.startswith(("http:", "https:", "data:", "/")):
                continue
            assert (frontend / src).is_file(), (name, src)
    for name in ("fds-export-worker.js", "ifc-parse-shard-worker.js"):
        worker = frontend / "src/workers" / name
        prefix = worker.read_text().split(");", 1)[0]
        for src in re.findall(r"'([^']+\.js)'", prefix):
            assert (worker.parent / src).is_file(), (name, src)


def test_engine_order_and_css_declarations_are_preserved():
    import hashlib
    import json
    import re

    frontend = ROOT / "frontend"
    scripts = re.findall(r'<script src="([^"]+)"', (frontend / "index.html").read_text(encoding="utf-8"))
    manifest = json.loads((frontend / "engine-scripts.json").read_text())
    for files in manifest.values():
        assert all((frontend / name).is_file() for name in files)
        indices = [scripts.index(name) for name in files]
        assert indices == sorted(indices)
    styles = frontend / "styles"
    manifest = json.loads((styles / "manifest.json").read_text())
    combined = "".join((styles / name).read_text(encoding="utf-8") for name in manifest["files"])
    assert hashlib.sha256(combined.encode()).hexdigest() == manifest["original_sha256"]


def test_frontend_transport_belongs_to_api_client():
    import re

    for directory in ("app", "components", "features", "viewer", "state"):
        for path in (ROOT / "frontend/src" / directory).rglob("*.js"):
            assert not re.search(r"\bfetch\s*\(", path.read_text(encoding="utf-8")), path
