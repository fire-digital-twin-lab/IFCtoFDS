"""Job service orchestrating queueing, worker subprocesses, timeouts, and cleanup."""

import json
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

        self.repository = JobRepository(root=self.root)
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

    def cleanup_orphaned_directories(self, max_age_s: Optional[int] = None) -> None:
        """Removes orphaned job-* directories on disk that are not registered in the database."""
        max_age = max_age_s if max_age_s is not None else self.retention_s
        now = time.time()
        known_dirs = {
            Path(j["directory"]).resolve()
            for j in self.repository.all_jobs()
            if j.get("directory")
        }
        try:
            for entry in self.root.glob("job-*"):
                if entry.is_dir():
                    resolved = entry.resolve()
                    if resolved not in known_dirs:
                        shutil.rmtree(resolved, ignore_errors=True)
                    elif max_age > 0 and (now - entry.stat().st_mtime) > max_age:
                        job_entry = next(
                            (j for j in self.repository.all_jobs() if Path(j.get("directory", "")).resolve() == resolved),
                            None
                        )
                        if job_entry and not job_entry.get("durable"):
                            shutil.rmtree(resolved, ignore_errors=True)
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
                process.wait(timeout=10)
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
                job["finished"] = time.time()
                self._stop(job["process"])
                self._terminal_diagnostic(job, "AbortError", "Job cancelled by user")
                self._cleanup(job)
                self.repository.set(jid, job)
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
            return {"id": jid, "state": "DELETED"}

    def close(self):
        self.closed = True
        self.wake.set()
        for jid in [j["id"] for j in self.repository.all_jobs()]:
            self.cancel(jid)
        if self.thread:
            self.thread.join(timeout=5)

    def _loop(self):
        while not self.closed:
            with self.lock:
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
                                shutil.rmtree(directory, ignore_errors=True)
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
                                if res_data.get("status") in ("MAPPING_VERIFIED", "SIMULATION_VERIFIED"):
                                    is_durable = True
                            except Exception:
                                pass
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
                        try:
                            # Capture stderr to error.txt if worker fails during startup
                            err_path = Path(queued["directory"]) / "error.txt"
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
            self.wake.wait(0.1)


# Backward compatibility alias
JobManager = JobService
