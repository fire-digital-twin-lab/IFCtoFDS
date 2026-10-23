"""Measure cancellation of a real worker after native conversion has started."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import psutil
from ifc_to_fds.modules.jobs.api import JobManager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    root = output / 'jobs'
    manager = JobManager(root=root)
    directory = root / 'sample'
    directory.mkdir()
    try:
        job = manager.submit([source], {'profile': 'mapping'}, directory)
        deadline = time.monotonic() + 60
        stage = None
        while time.monotonic() < deadline:
            snapshot = manager.snapshot(job['id'])
            assert snapshot['state'] in ('QUEUED', 'RUNNING'), snapshot
            try:
                stage = json.loads((directory / 'progress.json').read_text(encoding='utf-8')).get('stage')
            except (FileNotFoundError, ValueError):
                pass
            if stage in ('IFC_GEOMETRY', 'MAPPING', 'SERIALIZATION', 'VALIDATION'):
                break
            time.sleep(0.05)
        else:
            raise TimeoutError('Worker did not reach native conversion within 60s')
        with manager.lock:
            process = manager.jobs[job['id']]['process']
            parent = psutil.Process(process.pid)
            owned = [parent, *parent.children(recursive=True)]
        started = time.perf_counter()
        cancelled = manager.cancel(job['id'])
        latency = time.perf_counter() - started
        assert cancelled['state'] == 'CANCELLED', cancelled
        deadline = time.monotonic() + 5
        while any(member.is_running() for member in owned) and time.monotonic() < deadline:
            time.sleep(0.02)
        remaining = [member.pid for member in owned if member.is_running()]
        assert not remaining, remaining
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
        manager.close()
        assert not manager.thread.is_alive()
        record = {'source': source.name, 'source_bytes': source.stat().st_size,
                  'source_sha256': source_hash, 'stage_at_cancel': stage,
                  'cancel_s': latency, 'state': cancelled['state'],
                  'owned_process_count': len(owned), 'remaining_processes': remaining,
                  'supervisor_alive_after_close': manager.thread.is_alive()}
        (output / 'results.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        print(json.dumps(record), flush=True)
    finally:
        manager.close()


if __name__ == '__main__':
    main()
