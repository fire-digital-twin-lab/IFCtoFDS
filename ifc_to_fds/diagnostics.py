"""Cross-cutting bounded diagnostics; no source geometry or mapping decisions."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
from pathlib import Path
from time import perf_counter
import traceback

_directory = ContextVar("execution_directory", default=None)


@contextmanager
def execution_scope(directory):
    token = _directory.set(Path(directory))
    try:
        yield
    finally:
        _directory.reset(token)


def progress(stage, state, elapsed_s=0):
    directory = _directory.get()
    if directory:
        value = dict(stage=stage, state=state, elapsed_s=elapsed_s)
        # Atomic replacement avoids a polling reader seeing partial JSON.
        temporary = directory / "progress.tmp"
        temporary.write_text(json.dumps(value), encoding="utf-8")
        temporary.replace(directory / "progress.json")


def operation(stage):
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            started = perf_counter()
            progress(stage, "RUNNING")
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                if not getattr(exc, "ifcfds_stage", None):
                    exc.ifcfds_stage = stage
                progress(exc.ifcfds_stage, "FAILED", perf_counter()-started)
                raise
            progress(stage, "COMPLETED", perf_counter()-started)
            return result
        return run
    return decorate


def failure_diagnostic(error, job_id):
    return dict(name=type(error).__name__, message=str(error)[:2000],
                stack="".join(traceback.format_exception(error))[-12000:],
                stage=getattr(error, "ifcfds_stage", "ARTIFACT"), jobId=job_id,
                entity=getattr(error, "ifcfds_entity", None))
