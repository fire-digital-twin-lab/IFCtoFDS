"""Cross-cutting bounded diagnostics; no source geometry or mapping decisions."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
import logging
from pathlib import Path
from time import perf_counter, sleep
import traceback
from typing import List, Optional, Tuple

_logger = logging.getLogger(__name__)


def _record_stage_event(directory: Path, stage: str, state: str, elapsed_s: float) -> None:
    """Write derived, language-neutral diagnostics without changing acceptance."""
    from ifc_to_fds.observability import DiagnosticEvent, append_event
    code = f"IFCFDS.STAGE.{state}" if state in ("RUNNING", "COMPLETED", "FAILED") else "IFCFDS.STAGE.STATUS"
    event = DiagnosticEvent(
        code=code,
        level="ERROR" if state == "FAILED" else "INFO",
        stage=stage,
        params={"stage": stage, "state": state, "elapsed_s": round(elapsed_s, 3)},
        job_id=directory.name,
    )
    append_event(directory, event)


_directory: ContextVar[Optional[Path]] = ContextVar("execution_directory", default=None)
_stage_stack: ContextVar[Tuple[Tuple[str, float], ...]] = ContextVar(
    "stage_stack", default=()
)


@contextmanager
def execution_scope(directory: Path | str):
    token = _directory.set(Path(directory))
    stack_token = _stage_stack.set(())
    try:
        yield
    finally:
        _stage_stack.reset(stack_token)
        _directory.reset(token)


def _safe_replace(source: Path, target: Path, max_attempts: int = 5):
    for attempt in range(max_attempts):
        try:
            source.replace(target)
            return
        except (PermissionError, OSError):
            if attempt == max_attempts - 1:
                try:
                    source.unlink(missing_ok=True)
                except OSError:
                    pass
                return
            sleep(0.005 * (2**attempt))


def progress(stage: str, state: str, elapsed_s: float = 0.0, **details):
    directory = _directory.get()
    if directory:
        value = dict(stage=stage, state=state, elapsed_s=elapsed_s, **details)
        # Atomic replacement avoids a polling reader seeing partial JSON.
        temporary = directory / "progress.tmp"
        temporary.write_text(json.dumps(value), encoding="utf-8")
        _safe_replace(temporary, directory / "progress.json")
        try:
            _record_stage_event(directory, stage, state, elapsed_s)
        except (OSError, ValueError, TypeError) as exc:
            _logger.warning("Could not write bilingual diagnostic event: %s", exc)


def operation(stage: str):
    def decorate(function):
        @wraps(function)
        def run(*args, **kwargs):
            started = perf_counter()
            stack: List[Tuple[str, float]] = list(_stage_stack.get())
            stack.append((stage, started))
            _stage_stack.set(tuple(stack))
            progress(stage, "RUNNING")
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                err_stage = getattr(exc, "ifcfds_stage", None)
                if not err_stage:
                    err_stage = stage
                    setattr(exc, "ifcfds_stage", stage)
                progress(str(err_stage), "FAILED", perf_counter() - started)
                raise
            finally:
                current: List[Tuple[str, float]] = list(_stage_stack.get())
                if current and current[-1][0] == stage:
                    current.pop()
                    _stage_stack.set(tuple(current))
            remaining = _stage_stack.get()
            if remaining:
                enclosing_stage, enclosing_started = remaining[-1]
                progress(enclosing_stage, "RUNNING", perf_counter() - enclosing_started)
            else:
                progress(stage, "COMPLETED", perf_counter() - started)
            return result

        return run

    return decorate


def failure_diagnostic(error, job_id):
    return dict(
        name=type(error).__name__,
        message=str(error)[:2000],
        stack="".join(traceback.format_exception(error))[-12000:],
        stage=getattr(error, "ifcfds_stage", "ARTIFACT"),
        jobId=job_id,
        entity=getattr(error, "ifcfds_entity", None),
    )
