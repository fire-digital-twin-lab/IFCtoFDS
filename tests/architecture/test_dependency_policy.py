"""Declared module graph, layer rules and explicit compatibility exceptions."""

import hashlib
import importlib
import json
from pathlib import Path

import pytest

from tests.support.imports import get_imported_modules
from tests.support.dependency_rules import import_violations, module_owner, public_exports

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / 'docs/architecture/dependency-policy.json').read_text())
COMPAT = json.loads((ROOT / 'docs/architecture/compatibility-imports.json').read_text())


def test_production_imports_follow_declared_policy():
    errors = []
    for path in (ROOT / 'ifc_to_fds').rglob('*.py'):
        source = path.relative_to(ROOT).with_suffix('').as_posix().replace('/', '.').removesuffix('.__init__')
        for target in get_imported_modules(path):
            for reason in import_violations(source, target, POLICY, COMPAT['facades']):
                errors.append(f'{source}: {target}: {reason}')
        if path.name == 'api.py':
            for target, _ in public_exports(path).values():
                owner, other = module_owner(source), module_owner(target)
                if owner != other and other:
                    assert other in POLICY['allowed_module_dependencies'][owner], (owner, other)
                    assert target.split('.')[3] in POLICY['public_surfaces'], (source, target)
    assert not errors, '\n'.join(sorted(set(errors)))


def test_compatibility_facades_are_reviewed_files_and_aliases_share_identity():
    for name, spec in COMPAT['facades'].items():
        path = ROOT / spec['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == spec['sha256'], f'Review compatibility change: {name}'
        if spec.get('target'):
            assert importlib.import_module(name) is importlib.import_module(spec['target']), name


@pytest.mark.parametrize('source,target,expected', [
    ('ifc_to_fds.modules.bim.application.ingest', 'ifc_to_fds.modules.geometry.api', None),
    ('ifc_to_fds.modules.bim.application.ingest', 'ifc_to_fds.modules.geometry.infrastructure.payload_store', 'private module import'),
    ('ifc_to_fds.modules.bim.domain.rules', 'ifcopenshell.geom', 'domain imports runtime or infrastructure'),
    ('ifc_to_fds.modules.jobs.application.new_code', 'ifc_to_fds.modules.jobs.infrastructure.sqlite_repository', 'application imports concrete implementation'),
    ('ifc_to_fds.modules.geometry.application.new_code', 'ifc_to_fds.modules.bim.api', 'undeclared module dependency'),
    ('ifc_to_fds.modules.bim.application.new_code', 'ifc_to_fds.geometry.mesh', 'legacy facade import'),
    ('ifc_to_fds.modules.bim.application.new_code', 'ifc_to_fds.modules.bim.factory', 'application imports concrete implementation'),
])
def test_rule_rejects_real_boundary_bypasses(source, target, expected):
    result = import_violations(source, target, POLICY, COMPAT['facades'])
    if expected is None:
        assert result == []
    else:
        assert expected in result
