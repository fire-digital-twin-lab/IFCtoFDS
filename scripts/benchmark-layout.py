"""Compare conversion/cache/RSS against an explicit pre-refactor source checkout.

Each sample runs in a fresh Python process, outside either source tree. Warm
samples reuse only the converter's disk cache; independent audit still rereads IFC.
Use --preview-only for a separate preview benchmark without retaining native
preview resources inside the conversion process.
"""
import argparse
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def worker(args):
    if args.traceback_interval:
        faulthandler.dump_traceback_later(args.traceback_interval, repeat=True)
    imported = time.perf_counter()
    # Preload both versions identically; this also avoids the known historical
    # inventory-first import cycle, which is covered separately by a regression.
    import ifcopenshell.geom
    import trimesh
    import ifc_to_fds.core.canonical
    import ifc_to_fds
    assert Path(ifc_to_fds.__file__).resolve().is_relative_to(args.package_root.resolve())
    if args.preview_only:
        from ifc_to_fds.geometry.preview import preview_model
        started = time.perf_counter()
        preview = preview_model([str(args.source[0].resolve())], args.run_directory)
        index = json.loads((args.run_directory / 'model_geometry.json').read_text(encoding='utf-8'))
        args.output.write_text(json.dumps({
            'import_s': started - imported, 'preview_s': time.perf_counter() - started,
            'preview_cache_hit': bool(preview.get('preview_cache_hit')),
            'geometry_sha256': index['sha256'],
            'rendered_elements': preview['rendered_elements'], 'bounds': preview['bounds'],
        }, indent=2), encoding='utf-8')
        return
    from ifc_to_fds.pipeline import convert
    from ifc_to_fds.runtime.diagnostics import execution_scope
    started = time.perf_counter()
    cpu_started = time.process_time()
    args.run_directory.mkdir(parents=True, exist_ok=True)
    with execution_scope(args.run_directory):
        result = convert([str(args.source[0].resolve())], {'profile': 'mapping'}, output_directory=args.run_directory)
    elapsed = time.perf_counter() - started
    # Retain the actual verdict, findings and entity diagnostics alongside the
    # timing sample; a successful process is not geometry acceptance.
    (args.run_directory / 'acceptance_report.json').write_text(
        json.dumps(result['report'], indent=2), encoding='utf-8'
    )
    fields = ('entity_key', 'source_id', 'global_id', 'step_id', 'mapping_strategy',
              'fds_representation', 'fds_primitive_ids', 'scope_decision', 'geometry_status')
    inventory = [{key: item.get(key) for key in fields} for item in result['inventory']['elements']]
    sample = {
        'import_s': started - imported,
        'convert_audit_s': elapsed,
        'convert_audit_cpu_s': time.process_time() - cpu_started,
        'stage_timings': result['timings'],
        'mapping_status': result['mapping_status'],
        'fds_sha256': hashlib.sha256(result['fds_text'].encode()).hexdigest(),
        'geometry_sha256': result['geometry_package']['sha256'],
        'inventory_sha256': digest(inventory), 'mep_sha256': digest(result['mep_graph']),
        'gates': {name: gate['status'] for name, gate in result['report']['gates'].items()},
    }
    args.output.write_text(json.dumps(sample, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root', type=Path)
    parser.add_argument('--current-root', type=Path, default=Path.cwd())
    parser.add_argument('--source', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('--traceback-interval', type=float, default=0,
                        help='Opt-in diagnostic watchdog; excluded from performance samples')
    parser.add_argument('--preview-only', action='store_true')
    parser.add_argument('--version', choices=('before', 'after'), action='append')
    parser.add_argument('--cache', choices=('cold', 'warm'), action='append')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--package-root', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--run-directory', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    if not args.baseline_root:
        parser.error('--baseline-root is required')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result_file = output / 'results.json'
    records = json.loads(result_file.read_text(encoding='utf-8')) if result_file.exists() else []
    compared = 0
    for source in args.source:
        source = source.resolve()
        for version, package in [('before', args.baseline_root.resolve()), ('after', args.current_root.resolve())]:
            if args.version and version not in args.version:
                continue
            for cache in args.cache or ('cold', 'warm'):
                directory = output / source.stem / version / cache
                cache_directory = directory.parent / ('preview-cache' if args.preview_only else 'cache')
                if cache == 'warm' and not cache_directory.is_dir():
                    raise ValueError(f'Warm sample requires a prior cold cache: {cache_directory}')
                directory.mkdir(parents=True, exist_ok=False)
                result_path = directory / 'result.json'
                env = {**os.environ, 'PYTHONPATH': str(package), 'IFCFDS_REFERENCE_CASES': '{}',
                       'IFCFDS_PREVIEW_CACHE': str(directory.parent / 'preview-cache'),
                       'IFCFDS_GEOMETRY_CACHE': str(directory.parent / 'cache')}
                command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--package-root', str(package),
                           '--source', str(source), '--output', str(result_path), '--run-directory', str(directory / 'run')]
                if args.preview_only:
                    command.append('--preview-only')
                if args.traceback_interval:
                    command.extend(['--traceback-interval', str(args.traceback_interval)])
                with (directory / 'worker.log').open('w', encoding='utf-8') as log:
                    process = subprocess.Popen(command, cwd=directory, env=env, stdout=log, stderr=log,
                                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    started, peak = time.monotonic(), 0
                    while process.poll() is None:
                        if time.monotonic() - started > args.timeout:
                            owned = psutil.Process(process.pid)
                            children = owned.children(recursive=True)
                            cpu_s = 0
                            for member in [owned, *children]:
                                try:
                                    times = member.cpu_times()
                                    cpu_s += times.user + times.system
                                except psutil.NoSuchProcess:
                                    pass
                            (directory / 'timeout.json').write_text(json.dumps({
                                'status': 'TIMEOUT', 'timeout_s': args.timeout,
                                'sampled_peak_rss_mib': peak / 1024**2,
                                'owned_cpu_s_at_timeout': cpu_s,
                            }, indent=2), encoding='utf-8')
                            for child in reversed(children):
                                try: child.kill()
                                except psutil.NoSuchProcess: pass
                            process.kill()
                            process.wait()
                            raise TimeoutError(f'{source.name}/{version}/{cache} exceeded {args.timeout}s')
                        try:
                            parent = psutil.Process(process.pid)
                            # Windows venv python.exe may be only a small redirector;
                            # include its native Python child and any owned workers.
                            total = 0
                            for member in [parent, *parent.children(recursive=True)]:
                                try: total += member.memory_info().rss
                                except psutil.NoSuchProcess: pass
                            peak = max(peak, total)
                        except psutil.NoSuchProcess: pass
                        time.sleep(0.05)
                    if process.returncode:
                        (directory / 'failure.json').write_text(json.dumps({
                            'status': 'FAILED', 'returncode': process.returncode,
                            'elapsed_s': time.monotonic() - started,
                            'sampled_peak_rss_mib': peak / 1024**2,
                        }, indent=2), encoding='utf-8')
                        raise RuntimeError(f'Worker exited {process.returncode}: {directory / "worker.log"}')
                record = json.loads(result_path.read_text(encoding='utf-8'))
                record.update(source=source.name, source_bytes=source.stat().st_size, version=version, cache=cache,
                              sampled_peak_rss_mib=peak / 1024**2)
                records.append(record)
                (output / 'results.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
                elapsed = record['preview_s'] if args.preview_only else record['convert_audit_s']
                print(source.name, version, cache, round(elapsed, 3), 's', flush=True)
        first = [r for r in records if r['source'] == source.name]
        for record in first[1:]:
            keys = ('geometry_sha256', 'rendered_elements', 'bounds') if args.preview_only else (
                'fds_sha256', 'geometry_sha256', 'inventory_sha256', 'mep_sha256', 'mapping_status', 'gates')
            for key in keys:
                assert record[key] == first[0][key], (source.name, record['version'], record['cache'], key)
            compared += 1
    print(f'{len(records)} samples recorded; {compared} available sample pairs have matching semantic fingerprints.')


if __name__ == '__main__':
    main()
