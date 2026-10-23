"""Compare full Python workflow evidence with an explicit pre-refactor package.

Only declared timing fields and the per-run output directory are normalized.
Findings, evidence, coverage, gates, identities and manifest contents remain exact.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import psutil


def normalize(value, output_root):
    if isinstance(value, dict):
        return {key: normalize(item, output_root) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item, output_root) for item in value]
    if isinstance(value, str):
        return value.replace(str(output_root), '<RUN_DIRECTORY>')
    return value


def differences(before, after, prefix=''):
    if type(before) is not type(after):
        return [prefix]
    if isinstance(before, dict):
        return [path for key in sorted(before.keys() | after.keys())
                for path in ([prefix + '/' + key] if key not in before or key not in after
                             else differences(before[key], after[key], prefix + '/' + key))]
    if isinstance(before, list):
        if len(before) != len(after):
            return [prefix]
        return [path for index, pair in enumerate(zip(before, after))
                for path in differences(*pair, prefix + '/' + str(index))]
    return [] if before == after else [prefix]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root', type=Path)
    parser.add_argument('--current-root', type=Path, default=Path.cwd())
    parser.add_argument('--source', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        # Historical inventory-first cycle is tested separately. Both versions
        # use the same preloads to compare the workflow after module startup.
        import ifcopenshell.geom
        import trimesh
        import ifc_to_fds.core.canonical
        import ifc_to_fds
        assert Path(ifc_to_fds.__file__).resolve().is_relative_to(args.current_root.resolve())
        from ifc_to_fds.pipeline import convert
        output = args.output.resolve()
        result = convert([str(args.source[0].resolve())], {'profile': 'mapping'},
                         output_directory=output / 'run')
        evidence = {key: result[key] for key in ('report', 'manifest', 'inventory', 'mep_graph', 'fds_text')}
        for value in evidence.values():
            if isinstance(value, dict):
                value.pop('timings', None)
        metrics = evidence['report'].get('metrics', {})
        metrics.pop('solver_s', None)
        metrics.pop('stage_timings', None)
        (output / 'evidence.json').write_text(
            json.dumps(normalize(evidence, output), ensure_ascii=False, indent=2), encoding='utf-8')
        return
    if not args.baseline_root:
        parser.error('--baseline-root is required')
    output = args.output.resolve()
    records = []
    for source in args.source:
        for version, package in [('before', args.baseline_root), ('after', args.current_root)]:
            directory = output / source.stem / version
            directory.mkdir(parents=True, exist_ok=False)
            env = {**os.environ, 'PYTHONPATH': str(package.resolve()), 'IFCFDS_REFERENCE_CASES': '{}',
                   'IFCFDS_GEOMETRY_CACHE': str(directory / 'cache')}
            with (directory / 'worker.log').open('w', encoding='utf-8') as log:
                process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), '--worker',
                     '--current-root', str(package.resolve()), '--source', str(source.resolve()),
                     '--output', str(directory)], cwd=directory, env=env,
                    stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                try:
                    process.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    try:
                        children = psutil.Process(process.pid).children(recursive=True)
                    except psutil.NoSuchProcess:
                        children = []
                    for child in reversed(children):
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                    process.kill()
                    process.wait()
                    raise
                assert process.returncode == 0, directory / 'worker.log'
        before = json.loads((output / source.stem / 'before/evidence.json').read_text(encoding='utf-8'))
        after = json.loads((output / source.stem / 'after/evidence.json').read_text(encoding='utf-8'))
        changed = differences(before, after)
        records.append({'source': source.name, 'status': 'FAIL' if changed else 'PASS', 'changed_paths': changed})
        (output / 'results.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
        assert not changed, (source.name, changed[:30])
        print(source.name, 'FULL_EVIDENCE_IDENTICAL', flush=True)


if __name__ == '__main__':
    main()
