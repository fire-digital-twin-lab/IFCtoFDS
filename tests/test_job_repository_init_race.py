"""Several processes opening the same brand-new jobs database must all succeed (server + workers at startup)."""

import multiprocessing
import tempfile
from pathlib import Path


def _open(args):
    root, barrier_time = args
    import time

    from ifc_to_fds.adapters.jobs.repository import JobRepository

    time.sleep(max(0.0, barrier_time - time.time()))  # start together
    try:
        JobRepository(root=root)
        return None
    except Exception as exc:  # report, do not crash the pool
        return f"{type(exc).__name__}: {exc}"


def test_concurrent_first_open_of_a_new_database_never_fails():
    import time

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=6) as pool:
        for _ in range(8):  # new directory each round: the race is on creating the database
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
                start = time.time() + 1.5
                errors = [e for e in pool.map(_open, [(root, start)] * 6) if e]
                assert not errors, errors
