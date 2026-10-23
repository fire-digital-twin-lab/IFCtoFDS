"""Job service orchestrating queueing, worker subprocesses, timeouts, and cleanup."""

import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
import psutil
from ifc_to_fds.modules.jobs.contracts import JobStore, WorkerProcesses, JobRetention



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
        *, repository: JobStore | None = None, processes: WorkerProcesses | None = None,
        retention: JobRetention | None = None, clock=None,
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

        # Legacy direct construction remains supported. Production bootstrap
        # supplies these dependencies through the module factory.
        if repository is None or processes is None or retention is None:
            from ifc_to_fds.modules.jobs.factory import local_dependencies
            defaults = local_dependencies(self.root, repository, processes, retention)
            repository = repository if repository is not None else defaults[0]
            processes = processes if processes is not None else defaults[1]
            retention = retention if retention is not None else defaults[2]
        self.repository = repository
        self.processes = processes
        self.retention = retention
        self.clock = clock or time.time
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.closed = False
        self.thread: Optional[threading.Thread] = None

        # Clean up stale directories and reconcile interrupted jobs on startup
        self.cleanup_orphaned_directories()
        self._reconcile_startup_jobs()

    @property
    def jobs(self):
        """Backward compatibility access to internal dict."""
        return self.repository.cache

    def can_accept(self) -> bool:
        """Determines whether a new job can be accepted without overflowing the queue."""
        with self.lock:
            return self.repository.count_pending() < (self.max_waiting + 1)

    def touch(self, jid: str) -> None:
        """Updates last_accessed timestamp to protect active downloads from retention deletion."""
        with self.lock:
            job = self.repository.get(jid)
            if job:
                job["last_accessed"] = self.clock()
                self.repository.set(jid, job)

    def cleanup_orphaned_directories(self, max_age_s=None):
        return self.retention.cleanup_orphaned_directories(self, max_age_s)

    def _reconcile_startup_jobs(self) -> None:
        """Transitions any jobs left in active states from a prior process to FAILED."""
        now = self.clock()
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
                created=self.clock(),
                started=None,
                finished=None,
                last_accessed=self.clock(),
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

    def _stop(self, process):
        return self.processes.stop(process)

    @staticmethod
    def _cleanup(job):
        directory = Path(job["directory"])
        for path in directory.glob("source-*.ifc"):
            path.unlink(missing_ok=True)
        (directory / "request.json").unlink(missing_ok=True)

    @staticmethod
    def _terminal_diagnostic(job, name, message):
        directory = Path(job["directory"])
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
        with self.lock:
            job = self.repository.get(jid)
            if job and job["state"] in ("QUEUED", "RUNNING"):
                job["state"] = "CANCELLED"
                job["finished"] = self.clock()
                self._stop(job["process"])
                self._terminal_diagnostic(job, "AbortError", "Job cancelled by user")
                self._cleanup(job)
                self.repository.set(jid, job)
            self.wake.set()
            return self.snapshot(jid)

    def delete_job(self, jid: str) -> Dict[str, Any]:
        """Explicitly deletes a job and purges its artifacts from disk."""
        with self.lock:
            job = self.repository.get(jid)
            if not job:
                raise KeyError(jid)
            if job["state"] in ("QUEUED", "RUNNING"):
                return self.cancel(jid)
            directory = Path(job["directory"]).resolve()
            if directory.parent == self.root.resolve():
                shutil.rmtree(directory, ignore_errors=True)
            self.repository.delete(jid)
            self.wake.set()
            return {"id": jid, "state": "DELETED"}

    def close(self):
        self.closed = True
        self.wake.set()
        for jid in [j["id"] for j in self.repository.all_jobs()]:
            self.cancel(jid)
        if self.thread:
            self.thread.join(timeout=5)

    def tick(self):
        """One synchronized queue/supervision step; returns the next wait delay."""
        has_running = False
        has_queued = False
        with self.lock:
            self.wake.clear()
            now = self.clock()
            self.retention.sweep(self, now)

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
                        total_rss = self.processes.rss(proc)
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
                            return 0
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                # Process deadline timeout
                if self.clock() - running["started"] > self.timeout_s:
                    self._stop(proc)
                    running.update(
                        state="TIMED_OUT",
                        error="Job deadline exceeded",
                        finished=self.clock(),
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
                            if res_data.get("status") in ("MAPPING_VERIFIED", "SIMULATION_VERIFIED"):
                                is_durable = True
                        except Exception:
                            pass
                        running.update(state="COMPLETED", finished=self.clock(), durable=is_durable)
                    else:
                        error = (
                            (directory / "error.txt").read_text(encoding="utf-8")
                            if (directory / "error.txt").exists()
                            else f"Worker exited {proc.returncode}"
                        )
                        running.update(
                            state="FAILED", error=error[:2000], finished=self.clock()
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
                        proc = self.processes.launch(queued["directory"])
                        queued.update(
                            state="RUNNING", started=self.clock(), process=proc
                        )
                        self.repository.set(queued["id"], queued)
                    except Exception as exc:
                        queued.update(
                            state="FAILED",
                            error=f"Failed to spawn worker: {exc}",
                            finished=self.clock(),
                        )
                        self._cleanup(queued)
                        self.repository.set(queued["id"], queued)

            # Check if there are further queued jobs
            has_queued = any(j.get("state") == "QUEUED" for j in self.repository.all_jobs())

        wait_timeout = 0.1 if (has_running or has_queued) else 5.0
        return wait_timeout

    def _loop(self):
        while not self.closed:
            self.wake.wait(self.tick())


# Backward compatibility alias
JobManager = JobService
