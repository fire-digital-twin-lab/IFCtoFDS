"""Job service orchestrating queueing, worker subprocesses, timeouts, and cleanup."""

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import psutil

from .repository import JobRepository

logger = logging.getLogger(__name__)


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
        self.repository = JobRepository(root=self.root)
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.closed = False
        self.thread: Optional[threading.Thread] = None

        # Clean up stale directories and reconcile interrupted jobs on startup.
        # NOTE: unregistered-dir sweep is NEVER run implicitly at boot -- the
        # service cannot distinguish a healthy DB from a restored/migrated one,
        # and mtime heuristics proved unreliable (repository WAL activity bumps
        # mtime during init itself). Pass prune_unregistered=True explicitly
        # (e.g. a future admin/maintenance endpoint) to sweep unregistered dirs.
        self.cleanup_orphaned_directories()
        self._reconcile_startup_jobs()

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
        """Updates last_accessed timestamp to protect active downloads from retention deletion."""
        with self.lock:
            job = self.repository.get(jid)
            if job:
                job["last_accessed"] = time.time()
                self.repository.set(jid, job)

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
        known_dirs = {
            Path(j["directory"]).resolve()
            for j in self.repository.all_jobs()
            if j.get("directory")
        }
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
                    elif max_age > 0 and (now - entry.stat().st_mtime) > max_age:
                        job_entry = next(
                            (j for j in self.repository.all_jobs() if Path(j.get("directory", "")).resolve() == resolved),
                            None
                        )
                        if job_entry and not job_entry.get("durable"):
                            if resolved.parent != root_resolved:
                                continue
                            _rmtree_logged(resolved)
                            self.repository.delete(job_entry["id"])
        except OSError:
            pass

    def _reconcile_startup_jobs(self) -> None:
        """Transitions any jobs left in active states from a prior process to FAILED."""
        now = time.time()
        with self.lock:
            for jid, job in self.repository.items():
                if job.get("state") in ("QUEUED", "RUNNING"):
                    job.update(
                        state="FAILED",
                        error="Process terminated unexpectedly during server restart",
                        finished=now,
                    )
                    self._terminal_diagnostic(
                        job, "AbortError", "Process terminated unexpectedly during server restart"
                    )
                    self._cleanup(job)
                    self.repository.set(jid, job)

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
            self.repository.set(jid, job)
            if self.thread is None:
                self.thread = threading.Thread(target=self._loop, daemon=True)
                self.thread.start()
            self.wake.set()
            return self.snapshot(jid)

    def snapshot(self, jid):
        with self.lock:
            return self.repository.snapshot(jid)

    def result(self, jid):
        with self.lock:
            return self.repository.read_result(jid)

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
        directory = Path(job["directory"])
        for path in directory.glob("source-*.ifc"):
            path.unlink(missing_ok=True)
        (directory / "request.json").unlink(missing_ok=True)

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
        (directory / "diagnostics.json").write_text(
            json.dumps(
                dict(
                    name=name,
                    message=message,
                    stage=progress.get("stage", "IFC_READ"),
                    jobId=job["id"],
                    stack="",
                    entity=None,
                )
            ),
            encoding="utf-8",
        )

    def cancel(self, jid):
        proc_to_stop = None
        was_active = False
        with self.lock:
            job = self.repository.get(jid)
            if job and job["state"] in ("QUEUED", "RUNNING"):
                job["state"] = "CANCELLED"
                job["finished"] = time.time()
                proc_to_stop = job.get("process")
                was_active = True
                self._terminal_diagnostic(job, "AbortError", "Job cancelled by user")
                self.repository.set(jid, job)
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

    def _loop(self):
        while not self.closed:
            has_running = False
            has_queued = False
            dirs_to_delete = []
            with self.lock:
                self.wake.clear()
                now = time.time()
                # 1. Retention sweep for non-durable jobs
                for jid, job in self.repository.items():
                    if job.get("durable"):
                        continue
                    if self.retention_s > 0:
                        last_active = max(job.get("finished") or now, job.get("last_accessed") or 0)
                        if last_active + self.retention_s < now:
                            directory = Path(job["directory"]).resolve()
                            if directory.parent == self.root.resolve():
                                dirs_to_delete.append(directory)
                            self.repository.delete(jid)

                # 2. Queue wait timeout sweep
                for queued in [j for j in self.repository.all_jobs() if j["state"] == "QUEUED"]:
                    if now - queued.get("created", now) > self.queue_timeout_s:
                        queued.update(
                            state="TIMED_OUT",
                            error="Job queue wait timeout exceeded",
                            finished=now,
                        )
                        self._terminal_diagnostic(
                            queued, "TimeoutError", "Job queue wait timeout exceeded"
                        )
                        self._cleanup(queued)
                        self.repository.set(queued["id"], queued)

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
                            running["peak_rss_bytes"] = max(running.get("peak_rss_bytes") or 0, total_rss)
                            if total_rss > self.max_memory_bytes:
                                self._stop(proc)
                                limit_mb = self.max_memory_bytes // (1024 * 1024)
                                used_mb = total_rss // (1024 * 1024)
                                running.update(
                                    state="FAILED",
                                    error=f"RESOURCE_EXHAUSTED: Memory limit exceeded ({used_mb} MiB > {limit_mb} MiB)",
                                    finished=now,
                                )
                                self._terminal_diagnostic(
                                    running, "ResourceExhaustedError", f"Memory limit exceeded: {used_mb} MiB > {limit_mb} MiB"
                                )
                                self._cleanup(running)
                                self.repository.set(running["id"], running)
                                continue
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                    # Process deadline timeout
                    if time.time() - running["started"] > self.timeout_s:
                        self._stop(proc)
                        running.update(
                            state="TIMED_OUT",
                            error="Job deadline exceeded",
                            finished=time.time(),
                        )
                        self._terminal_diagnostic(
                            running, "TimeoutError", "Job deadline exceeded"
                        )
                        self._cleanup(running)
                        self.repository.set(running["id"], running)
                    elif proc.poll() is not None:
                        directory = Path(running["directory"])
                        if (
                            proc.returncode == 0
                            and (directory / "result.json").exists()
                        ):
                            is_durable = running.get("durable", False)
                            try:
                                res_data = json.loads((directory / "result.json").read_text(encoding="utf-8"))
                                if not isinstance(res_data, dict):
                                    raise ValueError("result.json is not a JSON object")
                                if running.get("mode") != "inventory" and not isinstance(res_data.get("status"), str):
                                    raise ValueError("result.json is missing a string 'status' field")
                                if res_data.get("status") == "MAPPING_VERIFIED":
                                    # NOTE (M1): SIMULATION_VERIFIED is never issued today
                                    # (ADR-0004 / AcceptanceReport.finalize dead code), so
                                    # narrowing to MAPPING_VERIFIED only is behavior-neutral.
                                    # Phase E must revisit durability promotion when
                                    # simulation verdicts become reachable.
                                    is_durable = True
                            except (OSError, ValueError) as exc:
                                result_error = f"Invalid result.json: {exc}"
                                running.update(
                                    state="FAILED",
                                    error=result_error[:2000],
                                    finished=time.time(),
                                )
                                self._terminal_diagnostic(
                                    running, "ValidationError", result_error
                                )
                            else:
                                running.update(state="COMPLETED", finished=time.time(), durable=is_durable)
                        else:
                            error = (
                                (directory / "error.txt").read_text(encoding="utf-8")
                                if (directory / "error.txt").exists()
                                else f"Worker exited {proc.returncode}"
                            )
                            running.update(
                                state="FAILED", error=error[:2000], finished=time.time()
                            )
                        self._cleanup(running)
                        self.repository.set(running["id"], running)
                    else:
                        pass
                else:
                    # 4. Dispatch next queued job
                    queued = next(
                        (
                            j
                            for j in self.repository.all_jobs()
                            if j["state"] == "QUEUED"
                        ),
                        None,
                    )
                    if queued:
                        has_running = True
                        try:
                            # Capture stderr to error.txt if worker fails during startup
                            err_path = Path(queued["directory"]) / "error.txt"
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
                                        queued["directory"],
                                    ],
                                    stdout=subprocess.DEVNULL,
                                    stderr=err_file,
                                    cwd=repo_root,
                                    env=worker_env,
                                    creationflags=getattr(
                                        subprocess, "CREATE_NO_WINDOW", 0
                                    ),
                                )
                            queued.update(
                                state="RUNNING", started=time.time(), process=proc
                            )
                            self.repository.set(queued["id"], queued)
                        except Exception as exc:
                            queued.update(
                                state="FAILED",
                                error=f"Failed to spawn worker: {exc}",
                                finished=time.time(),
                            )
                            self._cleanup(queued)
                            self.repository.set(queued["id"], queued)

                # Check if there are further queued jobs
                has_queued = any(j.get("state") == "QUEUED" for j in self.repository.all_jobs())

            # Perform heavy I/O outside self.lock
            for d in dirs_to_delete:
                _rmtree_logged(d)

            wait_timeout = 0.1 if (has_running or has_queued) else 5.0
            self.wake.wait(wait_timeout)


# Backward compatibility alias
JobManager = JobService
