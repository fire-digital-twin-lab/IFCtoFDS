"""Architecture policy shared by positive and negative boundary checks."""

import ast


def module_owner(name):
    parts = name.split('.')
    return parts[2] if parts[:2] == ['ifc_to_fds', 'modules'] and len(parts) > 2 else None


def import_violations(source, target, policy, facades):
    if source in facades:
        return []
    errors = []
    parts = source.split('.')
    owner, other = module_owner(source), module_owner(target)
    role = parts[3] if owner and len(parts) > 3 else None
    exceptions = {(e['source'], e['target']) for e in policy['layer_exceptions']}
    permitted_bridge = any(source == a and (target == b or target.startswith(b+'.')) for a,b in exceptions)
    if target.startswith(tuple('ifc_to_fds.'+p+'.' for p in policy['legacy_roots'])) or target in {'ifc_to_fds.'+p for p in policy['legacy_roots']}:
        errors.append('legacy facade import')
    if owner != other and other in policy['allowed_module_dependencies']:
        surface = target.split('.')[3:4]
        factory = source.startswith('ifc_to_fds.bootstrap.') and any(target == f or target.startswith(f+'.') for f in policy['module_factories'])
        if not factory and (not surface or surface[0] not in policy['public_surfaces']):
            errors.append('private module import')
        if owner and other not in policy['allowed_module_dependencies'][owner]:
            errors.append('undeclared module dependency')
    domain = source.startswith('ifc_to_fds.domain.') or role == 'domain'
    if domain:
        forbidden = ('ifcopenshell', 'fastapi', 'starlette', 'uvicorn', 'subprocess', 'sqlite3', 'httpx', 'requests', 'ifc_to_fds.application', 'ifc_to_fds.adapters', 'ifc_to_fds.interfaces', 'ifc_to_fds.bootstrap', 'ifc_to_fds.runtime')
        # Normalization is pure and is also used for semantic MEP comparison.
        if target != 'ifc_to_fds.runtime.normalization' and not target.startswith('ifc_to_fds.runtime.normalization.'):
            if any(target == x or target.startswith(x+'.') for x in forbidden):
                errors.append('domain imports runtime or infrastructure')
        if other and '.contracts' not in target and ('.application.' in target or '.infrastructure.' in target or '.api' in target):
            errors.append('domain imports runtime module API')
    if role == 'application' and not permitted_bridge:
        if owner == other and ('.infrastructure.' in target or target.endswith('.factory') or '.factory.' in target):
            errors.append('application imports concrete implementation')
        if target.startswith(('ifc_to_fds.bootstrap', 'ifc_to_fds.interfaces', 'ifc_to_fds.application')):
            errors.append('module application imports outer orchestration')
    return errors


def public_exports(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_EXPORTS' for t in node.targets):
            return ast.literal_eval(node.value)
    return {}
