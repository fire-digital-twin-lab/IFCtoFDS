"""Job service orchestrating queueing, worker subprocesses, timeouts, and cleanup."""

import json
import logging
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
import psutil

from .repository import JobPersistenceError, JobRepository
from .exclusive_lock import ExclusiveJobRootLock
from .result_contract import validate_job_result
from .evidence_index import verify_evidence_index

logger = logging.getLogger(__name__)


class ArtifactLeaseConflict(RuntimeError):
    """Job artifacts are currently being streamed and may not be purged."""


def _rmtree_logged(path: Path) -> None:
    """Best-effort shutil.rmtree that logs failures and retries with backoff.

    Replaces shutil.rmtree(..., ignore_errors=True) so failures leave a signal
    instead of succeeding silently. Never raises; success-path behavior is
    unchanged (single rmtree call, no waiting, no log output). Retries up to
    3 times (0.1s, 0.5s) to ride out transient Windows file locks.
    """
    failed = False

    def _onexc(func, failed_path, exc_info):
        nonlocal failed
        failed = True
        exc = exc_info[1] if exc_info else None
        logger.warning("Failed to remove %s (%s): %s", failed_path, func, exc)

    for attempt in (1, 2, 3):
        failed = False
        try:
            try:
                shutil.rmtree(path, onexc=_onexc)
            except TypeError:
                # Python 3.10/3.11: shutil.rmtree has no onexc kwarg
                # (added in 3.12); onerror accepts the same
                # (function, path, exc_info) callback signature.
                shutil.rmtree(path, onerror=_onexc)
        except OSError as exc:
            failed = True
            logger.warning("Failed to remove directory tree %s: %s", path, exc)
        if not failed:
            return
        if attempt == 1:
            time.sleep(0.1)
        elif attempt == 2:
            time.sleep(0.5)
    logger.warning("Gave up removing directory tree %s after retries", path)


class JobService:
    """Manages job submission, background execution, cancellation, and retention."""

    def __init__(
        self,
        root: Optional[Path | str] = None,
        max_waiting: int = 2,
        timeout_s: int = 1800,
        retention_s: int = 3600,
        max_memory_mb: Optional[int] = None,
        queue_timeout_s: int = 1800,
    ):
        self.root = Path(
            root or os.environ.get("IFCFDS_JOB_ROOT", str(Path.cwd() / ".jobs"))
        ).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_waiting = max_waiting
        self.timeout_s = timeout_s
        self.retention_s = int(os.environ.get("IFCFDS_JOB_RETENTION_S", str(retention_s)))
        max_mem = int(os.environ.get("IFCFDS_WORKER_MAX_MEMORY_MB", str(max_memory_mb or 4096)))
        self.max_memory_bytes = max_mem * 1024 * 1024
        self.queue_timeout_s = int(os.environ.get("IFCFDS_QUEUE_TIMEOUT_S", str(queue_timeout_s)))

        self.boot_time = time.time()  # informational; sweep guards no longer use it
        # One OS-level scheduler owner per local SQLite root in network modes.
        # Local/test keeps historical independent fixture behavior.
        self._root_lock = (
            ExclusiveJobRootLock(self.root)
            if os.getenv("IFCFDS_ENV", "local").strip().lower()
            in ("staging", "production")
            else None
        )
        try:
            self.repository = JobRepository(root=self.root)
        except (OSError, sqlite3.Error, RuntimeError, ValueError, KeyError, TypeError):
            if self._root_lock is not None:
                self._root_lock.release()
            raise
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.closed = False
        self.thread: Optional[threading.Thread] = None
        # Private retry intents: never publish a terminal status in RAM until
        # its SQLite transition commits. Preserve the original failure reason
        # even if the killed process has exited before the next scheduler tick.
        self._pending_terminal: Dict[str, Dict[str, Any]] = {}
        # Stopped-worker diagnostic writes can fail before the SQLite verdict.
        # Retry the same diagnostic before publishing the preserved terminal intent.
        self._pending_diagnostic: Dict[str, tuple[str, str]] = {}
        # Protect file responses between route validation and final ASGI send.
        self._artifact_leases: Dict[str, int] = {}

        # Clean up stale directories and reconcile interrupted jobs on startup.
        # NOTE: unregistered-dir sweep is NEVER run implicitly at boot -- the
        # service cannot distinguish a healthy DB from a restored/migrated one,
        # and mtime heuristics proved unreliable (repository WAL activity bumps
        # mtime during init itself). Pass prune_unregistered=True explicitly
        # (e.g. a future admin/maintenance endpoint) to sweep unregistered dirs.
        try:
            self.cleanup_orphaned_directories()
            self._reconcile_startup_jobs()
        except (OSError, sqlite3.Error, RuntimeError, ValueError, KeyError, TypeError):
            if self._root_lock is not None:
                self._root_lock.release()
            raise

    @property
    def jobs(self):
        """Read-only view of the internal job registry (do not mutate).

        Backward-compatibility accessor; callers must treat the returned
        mapping as read-only and use repository methods for writes.
        The DELETE endpoint reads via .get() under manager.lock.
        """
        return self.repository._jobs

    def can_accept(self) -> bool:
        """Determines whether a new job can be accepted without overflowing the queue."""
        with self.lock:
            return self.repository.count_pending() < (self.max_waiting + 1)

    def touch(self, jid: str) -> None:
        """Commit access time before publishing an extension to job retention.

        A failed SQLite write must not leave a newer RAM timestamp that masks
        an old durable value and allows artifacts to disappear after restart.
        """
        with self.lock:
            job = self.repository.get(jid)
            if job:
                touched = dict(job)
                touched["last_accessed"] = time.time()
                self.repository.set_durable(jid, touched)

    def acquire_artifact_lease(self, jid: str) -> None:
        """Pin a registered job until its artifact response completes."""
        with self.lock:
            if not self.repository.contains(jid):
                raise KeyError(jid)
            self._artifact_leases[jid] = self._artifact_leases.get(jid, 0) + 1

    def release_artifact_lease(self, jid: str) -> None:
        """Release a pin even if the client disconnects during streaming."""
        with self.lock:
            count = self._artifact_leases.get(jid, 0)
            if count <= 1:
                self._artifact_leases.pop(jid, None)
            else:
                self._artifact_leases[jid] = count - 1
            self.wake.set()

    def cleanup_orphaned_directories(
        self, max_age_s: Optional[int] = None,
        prune_unregistered: bool = False,
    ) -> None:
        """Retention sweep for registered jobs; unregistered-dir purge is opt-in.

        Unregistered job-* directories are NEVER removed unless the caller
        passes prune_unregistered=True explicitly: at boot the service cannot
        distinguish a healthy DB from a restored/migrated one, and mtime
        heuristics proved unreliable (repository WAL activity bumps mtime
        during init itself). Retention for DB-registered non-durable jobs
        always applies.

        Manual purge (operator): stop the service, then call
        cleanup_orphaned_directories(prune_unregistered=True) — e.g. via
        ``python -m`` or a future admin/maintenance endpoint — to purge
        unregistered job-* directories.
        """
        if not prune_unregistered:
            known = {
                Path(j["directory"]).resolve()
                for j in self.repository.all_jobs()
                if j.get("directory")
            }
            preserved = sorted(
                p.name for p in self.root.glob("job-*")
                if p.is_dir() and p.resolve() not in known
            )
            sample = ", ".join(preserved[:10])
            if len(preserved) > 10:
                sample += ", ..."
            logger.warning(
                "Skipping unregistered-dir sweep: implicit boot sweep is "
                "disabled to protect pre-upgrade artifacts under %s "
                "(preserved %d unregistered job-* dir(s)%s); pass "
                "prune_unregistered=True explicitly to purge them",
                self.root,
                len(preserved),
                f": {sample}" if sample else "",
            )
        max_age = max_age_s if max_age_s is not None else self.retention_s
        now = time.time()
        root_resolved = self.root.resolve()
        known_by_dir = {
            Path(j["directory"]).resolve(): j
            for j in self.repository.all_jobs()
            if j.get("directory")
        }
        known_dirs = set(known_by_dir)
        try:
            for entry in self.root.glob("job-*"):
                if entry.is_dir():
                    resolved = entry.resolve()
                    if resolved.parent != root_resolved:
                        continue
                    if resolved not in known_dirs:
                        if not prune_unregistered:
                            continue
                        # Explicit opt-in prune: no mtime guard. (A boot_time
                        # guard here caused flakes: a dir created milliseconds
                        # before init can carry a newer mtime than boot_time on
                        # coarse-grained filesystems.)
                        _rmtree_logged(resolved)
                    elif max_age > 0:
                        job_entry = known_by_dir.get(resolved)
                        if (
                            job_entry is None
                            or job_entry.get("durable")
                            or job_entry.get("state") in ("QUEUED", "RUNNING")
                        ):
                            continue
                        # Access timestamps are committed to SQLite; reading
                        # an artifact does not update directory mtime.
                        # A restarted process must use the same retention clock
                        # as the live scheduler, never filesystem heuristics.
                        timestamps = [
                            float(value)
                            for value in (
                                job_entry.get("created"),
                                job_entry.get("finished"),
                                job_entry.get("last_accessed"),
                            )
                            if type(value) in (int, float) and math.isfinite(value)
                        ]
                        if not timestamps or now - max(timestamps) <= max_age:
                            continue
                        with self.lock:
                            if self._artifact_leases.get(job_entry["id"], 0):
                                continue
                            try:
                                self.repository.delete(job_entry["id"])
                            except JobPersistenceError:
                                logger.exception(
                                    "Preserving retained job %s because SQLite deletion failed",
                                    job_entry["id"],
                                )
                                continue
                            _rmtree_logged(resolved)
        except OSError:
            pass

    def _reconcile_startup_jobs(self) -> None:
        """Transitions any jobs left in active states from a prior process to FAILED."""
        now = time.time()
        with self.lock:
            for jid, job in self.repository.items():
                if job.get("state") in ("QUEUED", "RUNNING"):
                    # Crash reconciliation must not mutate the cached state or
                    # delete inputs before SQLite acknowledges the transition.
                    recovered = dict(job)
                    recovered.update(
                        state="FAILED",
                        error="Process terminated unexpectedly during server restart",
                        finished=now,
                    )
                    try:
                        self._terminal_diagnostic(
                            recovered, "AbortError", "Process terminated unexpectedly during server restart"
                        )
                    except OSError:
                        # e.g. job directory already gone: must not abort service boot.
                        logger.exception(
                            "Cannot write startup diagnostic for job %s; failing it without one", jid
                        )
                    try:
                        self.repository.set_durable(jid, recovered)
                    except JobPersistenceError:
                        logger.exception(
                            "Preserving input for job %s: startup reconciliation not durable", jid
                        )
                    else:
                        self._cleanup(recovered)

    def submit(self, paths, configuration, directory, mode="convert"):
        with self.lock:
            if not self.can_accept():
                raise OverflowError("Job queue is full")
            jid = uuid.uuid4().hex
            durable = bool(
                (configuration or {}).get("preserve_artifacts")
                or (configuration or {}).get("durable")
            )
            job = dict(
                id=jid,
                state="QUEUED",
                directory=str(directory),
                mode=mode,
                created=time.time(),
                started=None,
                finished=None,
                last_accessed=time.time(),
                error=None,
                process=None,
                durable=durable,
                retention_s=self.retention_s,
                peak_rss_bytes=None,
            )
            Path(directory, "request.json").write_text(
                json.dumps(
                    dict(
                        job_id=jid,
                        paths=[str(p) for p in paths],
                        configuration=configuration,
                        mode=mode,
                    )
                ),
                encoding="utf-8",
            )
            # Admission must fail closed if SQLite cannot retain this job.
            # Do not start the worker or expose the job until persistence commits.
            self.repository.register(jid, job)
            if self.thread is None:
                self.thread = threading.Thread(target=self._loop, daemon=True)
                self.thread.start()
            self.wake.set()
            return self.snapshot(jid)

    def snapshot(self, jid):
        with self.lock:
            return self.repository.snapshot(jid)

    def result(self, jid):
        # Only the in-memory job snapshot needs synchronization. JSON parsing,
        # file hashing and cross-file audit checks must not hold the scheduler
        # lock: a large FDS bundle could otherwise block all job progress.
        with self.lock:
            job = self.repository.get(jid)
            if job is None:
                raise KeyError(jid)
            snapshot = dict(job)
        return self.repository.read_result(jid, job=snapshot)

    @staticmethod
    def _stop(process):
        if process and process.poll() is None:
            try:
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                parent.kill()
                process.wait(timeout=2)
            except (psutil.NoSuchProcess, subprocess.TimeoutExpired):
                pass

    @staticmethod
    def _cleanup(job):
        """Best-effort input cleanup; a locked file must not stop the scheduler.

        The job transition has already committed to SQLite. Keep the error
        visible for operator remediation, but never convert a terminal job to
        an API 500 or terminate the supervisor thread due to PermissionError.
        """
        directory = Path(job["directory"])
        try:
            inputs = list(directory.glob("source-*.ifc"))
        except OSError:
            logger.exception(
                "Cannot enumerate inputs for terminal job %s; retaining directory",
                job.get("id"),
            )
            inputs = []
        for path in [*inputs, directory / "request.json"]:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Cannot delete terminal input %s for job %s; manual cleanup may be required",
                    path.name,
                    job.get("id"),
                )

    @staticmethod
    def _terminal_diagnostic(job, name, message):
        directory = Path(job["directory"])
        # M2: never clobber a richer worker-written diagnostics.json. The
        # invalid-result.json path reaches here after the worker may already
        # have reported; keep the first (worker) diagnostic and skip.
        diag_path = directory / "diagnostics.json"
        if diag_path.is_file():
            logger.debug(
                "Preserving existing diagnostics.json for job %s; skipping %s",
                job["id"], name,
            )
            return
        try:
            progress = json.loads(
                (directory / "progress.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            progress = {}
        # A direct write_text() can publish a truncated diagnostics.json if
        # the filesystem fails mid-write. The next retry sees is_file() and
        # would incorrectly treat that partial file as complete evidence.
        # Build and fsync a private temp file, then publish it using a hard
        # link: atomic create-if-absent, never replacing a worker diagnostic.
        content = json.dumps(
            dict(
                name=name,
                message=message,
                stage=progress.get("stage", "IFC_READ"),
                jobId=job["id"],
                stack="",
                entity=None,
            )
        )
        temporary = directory / f".diagnostics-{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, diag_path)
            except FileExistsError:
                logger.debug(
                    "Preserving concurrent worker diagnostic for job %s",
                    job["id"],
                )
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # An already published diagnostic is valid despite temp
                # cleanup failure. Keep the failure visible for operators.
                logger.exception(
                    "Cannot remove temporary terminal diagnostic for job %s",
                    job["id"],
                )

    def cancel(self, jid):
        proc_to_stop = None
        was_active = False
        with self.lock:
            job = self.repository.get(jid)
            if job and job["state"] in ("QUEUED", "RUNNING"):
                # Do not mutate the cached dictionary: a failed database write
                # must leave both cache and SQLite in the original state.
                cancelled = dict(job)
                cancelled["state"] = "CANCELLED"
                cancelled["finished"] = time.time()
                self.repository.set_durable(jid, cancelled)
                self._pending_terminal.pop(jid, None)
                self._pending_diagnostic.pop(jid, None)
                proc_to_stop = job.get("process")
                was_active = True
                try:
                    self._terminal_diagnostic(
                        cancelled, "AbortError", "Job cancelled by user"
                    )
                except OSError:
                    # Cancellation has already committed. An unavailable disk
                    # must not turn a successful cancellation into HTTP 500.
                    logger.exception(
                        "Could not write cancellation diagnostic for job %s "
                        "after SQLite committed CANCELLED",
                        jid,
                    )
            self.wake.set()
        if proc_to_stop:
            self._stop(proc_to_stop)
        with self.lock:
            job = self.repository.get(jid)
            if job and was_active:
                self._cleanup(job)
            return self.snapshot(jid)

    def delete_job(self, jid: str, purge: bool = False) -> Dict[str, Any]:
        """Cancels active jobs; purges terminal jobs only when purge=True."""
        dir_to_purge = None
        with self.lock:
            job = self.repository.get(jid)
            if not job:
                raise KeyError(jid)
            if job["state"] in ("QUEUED", "RUNNING"):
                # Intentional safe downgrade: active jobs are cancelled even when
                # purge=True; the artifacts directory is preserved (cancel never
                # purges) and the row remains CANCELLED. Terminal-job purge
                # semantics below are unchanged.
                return self.cancel(jid)
            if not purge:
                return self.snapshot(jid)
            if self._artifact_leases.get(jid, 0):
                raise ArtifactLeaseConflict("Artifact download in progress; retry purge")
            directory = Path(job["directory"]).resolve()
            if directory.parent == self.root.resolve():
                dir_to_purge = directory
            self.repository.delete(jid)
            self.wake.set()
            result = {"id": jid, "state": "DELETED"}
        if dir_to_purge:
            _rmtree_logged(dir_to_purge)
        return result

    def close(self):
        self.closed = True
        self.wake.set()
        for jid in [j["id"] for j in self.repository.all_jobs()]:
            self.cancel(jid)
        if self.thread:
            self.thread.join(timeout=5)
        if self._root_lock is not None:
            if self.thread is not None and self.thread.is_alive():
                # Never release exclusivity while a supervisor can still
                # mutate SQLite, even after the close timeout.
                raise RuntimeError("Scheduler still active; exclusive lock retained")
            self._root_lock.release()

    def _finish_stopped_worker(
        self,
        terminal: Dict[str, Any],
        diagnostic_name: str,
        diagnostic_message: str,
        storage_failure_message: str,
    ) -> None:
        """Keep a stopped worker's original verdict through diagnostic/SQLite I/O.

        The worker has already been killed at this point. If the diagnostic
        cannot be written, a subsequent scheduler turn must NOT replace the
        original resource/deadline reason with a generic worker-exit error.
        """
        jid = terminal["id"]
        try:
            self._terminal_diagnostic(terminal, diagnostic_name, diagnostic_message)
        except OSError:
            self._pending_terminal[jid] = terminal
            self._pending_diagnostic[jid] = (diagnostic_name, diagnostic_message)
            logger.exception(
                "Deferring stopped worker %s terminal verdict until diagnostic I/O recovers",
                jid,
            )
            return
        try:
            self.repository.set_durable(jid, terminal)
        except JobPersistenceError:
            self._pending_terminal[jid] = terminal
            logger.exception(storage_failure_message, jid)
        else:
            self._cleanup(terminal)

    def _retry_pending_terminals(self) -> bool:
        """Retry a stopped worker's original terminal verdict after SQLite failure.

        Returns True if any pending intent existed, so dispatch can be deferred
        for one scheduler turn even after storage recovers. The pending data is
        private to this process; after a server crash startup reconciliation
        marks interrupted jobs FAILED without falsely claiming a prior verdict.
        """
        with self.lock:
            if not self._pending_terminal:
                return False
            for jid, terminal in list(self._pending_terminal.items()):
                current = self.repository.get(jid)
                if not current or current.get("state") not in ("QUEUED", "RUNNING"):
                    self._pending_terminal.pop(jid, None)
                    self._pending_diagnostic.pop(jid, None)
                    continue
                diagnostic = self._pending_diagnostic.get(jid)
                if diagnostic is not None:
                    try:
                        self._terminal_diagnostic(terminal, *diagnostic)
                    except OSError:
                        logger.exception(
                            "Retry of stopped worker %s diagnostic failed; preserving verdict",
                            jid,
                        )
                        continue
                    self._pending_diagnostic.pop(jid, None)
                try:
                    self.repository.set_durable(jid, terminal)
                except JobPersistenceError:
                    logger.exception(
                        "Retry of original terminal verdict for job %s failed", jid
                    )
                else:
                    self._pending_terminal.pop(jid, None)
                    self._cleanup(terminal)
            return True

    def _loop(self):
        """Retry recoverable scheduler filesystem errors without losing job state.

        A diagnostics.json write may fail with OSError before SQLite is
        updated. Letting it escape would terminate the daemon thread and
        strand queued jobs indefinitely. The next pass retries against the
        original durable state; no terminal verdict is fabricated.
        """
        retry_delay_s = 0.1
        while not self.closed:
            try:
                self._run_loop_until_io_failure()
            except OSError:
                logger.exception(
                    "Scheduler I/O failure; preserving durable job state and retrying"
                )
                # Back off even when a wakeup was left set by another path.
                self.wake.clear()
                self.wake.wait(retry_delay_s)
                retry_delay_s = min(retry_delay_s * 2, 5.0)

    def _run_loop_until_io_failure(self):
        while not self.closed:
            if self._retry_pending_terminals():
                # Do not spin on locked/full storage or dispatch another job
                # while an already-stopped worker has an uncommitted verdict.
                self.wake.wait(0.1)
                continue
            has_running = False
            has_queued = False
            dirs_to_delete = []
            # An expired QUEUED row whose SQLite transition failed must not be
            # dispatched during this turn; it is retried at the next wakeup.
            blocked_dispatch_ids = set()
            with self.lock:
                self.wake.clear()
                now = time.time()
                # 1. Retention sweep for non-durable jobs
                for jid, job in self.repository.items():
                    if job.get("durable") or self._artifact_leases.get(jid, 0):
                        continue
                    if self.retention_s > 0:
                        last_active = max(job.get("finished") or now, job.get("last_accessed") or 0)
                        if last_active + self.retention_s < now:
                            directory = Path(job["directory"]).resolve()
                            try:
                                self.repository.delete(jid)
                            except JobPersistenceError:
                                logger.exception(
                                    "Keeping job %s after SQLite retention deletion failed", jid
                                )
                            else:
                                if directory.parent == self.root.resolve():
                                    dirs_to_delete.append(directory)

                # 2. Queue wait timeout sweep
                for queued in [j for j in self.repository.all_jobs() if j["state"] == "QUEUED"]:
                    if now - queued.get("created", now) > self.queue_timeout_s:
                        timed_out = dict(queued)
                        timed_out.update(
                            state="TIMED_OUT",
                            error="Job queue wait timeout exceeded",
                            finished=now,
                        )
                        self._terminal_diagnostic(
                            timed_out, "TimeoutError", "Job queue wait timeout exceeded"
                        )
                        try:
                            self.repository.set_durable(timed_out["id"], timed_out)
                        except JobPersistenceError:
                            blocked_dispatch_ids.add(queued["id"])
                            logger.exception(
                                "Keeping job %s QUEUED after queue timeout persistence failure",
                                queued["id"],
                            )
                        else:
                            self._cleanup(timed_out)

                # 3. Active running worker supervision
                running = next(
                    (j for j in self.repository.all_jobs() if j["state"] == "RUNNING"),
                    None,
                )
                if running:
                    has_running = True
                    proc = running["process"]
                    # Memory RSS monitoring
                    if proc and proc.pid:
                        try:
                            parent_proc = psutil.Process(proc.pid)
                            total_rss = parent_proc.memory_info().rss
                            for child in parent_proc.children(recursive=True):
                                try:
                                    total_rss += child.memory_info().rss
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    pass
                            peak_rss = max(running.get("peak_rss_bytes") or 0, total_rss)
                            if total_rss > self.max_memory_bytes:
                                self._stop(proc)
                                limit_mb = self.max_memory_bytes // (1024 * 1024)
                                used_mb = total_rss // (1024 * 1024)
                                exhausted = dict(running)
                                exhausted.update(
                                    state="FAILED",
                                    error=f"RESOURCE_EXHAUSTED: Memory limit exceeded ({used_mb} MiB > {limit_mb} MiB)",
                                    finished=now,
                                    peak_rss_bytes=peak_rss,
                                )
                                self._finish_stopped_worker(
                                    exhausted,
                                    "ResourceExhaustedError",
                                    f"Memory limit exceeded: {used_mb} MiB > {limit_mb} MiB",
                                    "Keeping job %s RUNNING after resource limit persistence failure",
                                )
                                continue
                            # The peak is monitoring metadata, not a terminal verdict.
                            # Cache may reflect it immediately, without changing job state.
                            running["peak_rss_bytes"] = peak_rss
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                    # A persisted RUNNING row may have no live Popen handle
                    # after restart or a failed scheduler transition. Never
                    # crash the supervisor thread by calling None.poll().
                    if proc is None or running.get("started") is None:
                        reason = "Running job has no worker handle or start timestamp"
                        missing = dict(running)
                        self._terminal_diagnostic(
                            missing, "WorkerProcessMissingError", reason
                        )
                        missing.update(
                            state="FAILED", error=reason, finished=time.time()
                        )
                        try:
                            self.repository.set_durable(missing["id"], missing)
                        except JobPersistenceError:
                            logger.exception(
                                "Keeping job %s RUNNING after missing worker persistence failure",
                                missing["id"],
                            )
                        else:
                            self._cleanup(missing)
                    # Process deadline timeout
                    elif time.time() - running["started"] > self.timeout_s:
                        self._stop(proc)
                        expired = dict(running)
                        expired.update(
                            state="TIMED_OUT",
                            error="Job deadline exceeded",
                            finished=time.time(),
                        )
                        self._finish_stopped_worker(
                            expired,
                            "TimeoutError",
                            "Job deadline exceeded",
                            "Keeping job %s RUNNING after deadline persistence failure",
                        )
                    elif proc.poll() is not None:
                        terminal = dict(running)
                        directory = Path(running["directory"])
                        if (
                            proc.returncode == 0
                            and (directory / "result.json").exists()
                        ):
                            is_durable = running.get("durable", False)
                            try:
                                res_data = json.loads((directory / "result.json").read_text(encoding="utf-8"))
                                mode = running.get("mode", "convert")
                                validate_job_result(mode, res_data)
                                verify_evidence_index(directory, mode, res_data)
                                if mode == "convert" and res_data["status"] == "MAPPING_VERIFIED":
                                    # NOTE (M1): SIMULATION_VERIFIED is never issued today
                                    # (ADR-0004 / AcceptanceReport.finalize dead code), so
                                    # narrowing to MAPPING_VERIFIED only is behavior-neutral.
                                    # Phase E must revisit durability promotion when
                                    # simulation verdicts become reachable.
                                    is_durable = True
                            except (OSError, ValueError) as exc:
                                result_error = f"Invalid result.json: {exc}"
                                # Publish terminal state only *after* the
                                # diagnostic is persisted: repository readers
                                # otherwise observe FAILED before evidence
                                # exists (reproduced on Windows CI).
                                self._terminal_diagnostic(
                                    terminal, "ValidationError", result_error
                                )
                                terminal.update(
                                    state="FAILED",
                                    error=result_error[:2000],
                                    finished=time.time(),
                                )
                            else:
                                terminal.update(state="COMPLETED", finished=time.time(), durable=is_durable)
                        else:
                            error = (
                                (directory / "error.txt").read_text(encoding="utf-8")
                                if (directory / "error.txt").exists()
                                else f"Worker exited {proc.returncode}"
                            )
                            terminal.update(
                                state="FAILED", error=error[:2000], finished=time.time()
                            )
                        # Preserve source and the original cached RUNNING state
                        # until SQLite has committed the terminal transition.
                        # A failed update will be retried on the next loop.
                        try:
                            self.repository.set_durable(terminal["id"], terminal)
                        except JobPersistenceError:
                            logger.exception(
                                "Keeping job %s RUNNING after terminal state storage failed",
                                terminal["id"],
                            )
                        else:
                            self._cleanup(terminal)
                    else:
                        pass
                else:
                    # 4. Dispatch next queued job
                    queued = next(
                        (
                            j
                            for j in self.repository.all_jobs()
                            if j["state"] == "QUEUED"
                            and j["id"] not in blocked_dispatch_ids
                        ),
                        None,
                    )
                    if queued:
                        # The worker cannot start until its RUNNING transition is
                        # durable. A failed SQLite write leaves the queue entry
                        # unchanged and does not create an untracked subprocess.
                        starting = dict(queued)
                        starting.update(
                            state="RUNNING", started=time.time(), process=None
                        )
                        try:
                            self.repository.set_durable(starting["id"], starting)
                        except JobPersistenceError:
                            logger.exception(
                                "Keeping job %s QUEUED: could not reserve worker startup",
                                queued["id"],
                            )
                        else:
                            has_running = True
                            try:
                                # Capture stderr to error.txt if worker fails during startup.
                                err_path = Path(starting["directory"]) / "error.txt"
                                worker_env = os.environ.copy()
                                worker_env.pop("IFCFDS_API_KEY", None)
                                repo_root = str(Path(__file__).resolve().parents[3])
                                existing_pythonpath = worker_env.get("PYTHONPATH", "")
                                worker_env["PYTHONPATH"] = (
                                    f"{repo_root}{os.pathsep}{existing_pythonpath}"
                                    if existing_pythonpath
                                    else repo_root
                                )
                                with open(err_path, "a", encoding="utf-8") as err_file:
                                    proc = subprocess.Popen(
                                        [
                                            sys.executable,
                                            "-m",
                                            "ifc_to_fds.jobs",
                                            starting["directory"],
                                        ],
                                        stdout=subprocess.DEVNULL,
                                        stderr=err_file,
                                        cwd=repo_root,
                                        env=worker_env,
                                        creationflags=getattr(
                                            subprocess, "CREATE_NO_WINDOW", 0
                                        ),
                                    )
                            except Exception as exc:
                                failed = dict(starting)
                                failed.update(
                                    state="FAILED",
                                    error=f"Failed to spawn worker: {exc}",
                                    finished=time.time(),
                                )
                                try:
                                    self._terminal_diagnostic(
                                        failed, "WorkerSpawnError", failed["error"]
                                    )
                                except OSError:
                                    logger.exception(
                                        "Could not write startup diagnostic for job %s",
                                        failed["id"],
                                    )
                                try:
                                    self.repository.set_durable(failed["id"], failed)
                                except JobPersistenceError:
                                    # Keep the original spawn error in a private
                                    # retry intent. A missing Popen handle must not
                                    # overwrite it with a generic error next turn.
                                    self._pending_terminal[failed["id"]] = failed
                                    logger.exception(
                                        "Preserving job %s after worker spawn failure "
                                        "could not be persisted", failed["id"]
                                    )
                                else:
                                    self._cleanup(failed)
                            else:
                                # Only the nonserializable process handle changes
                                # after the RUNNING record has committed.
                                starting["process"] = proc

                # Check if there are further queued jobs
                has_queued = any(j.get("state") == "QUEUED" for j in self.repository.all_jobs())

            # Perform heavy I/O outside self.lock
            for d in dirs_to_delete:
                _rmtree_logged(d)

            wait_timeout = 0.1 if (has_running or has_queued) else 5.0
            self.wake.wait(wait_timeout)


# Backward compatibility alias
JobManager = JobService
