"""Job service orchestrating queueing, worker subprocesses, timeouts, and cleanup."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
import psutil

from .repository import JobRepository


class JobService:
    """Manages job submission, background execution, cancellation, and retention."""

    def __init__(self, root=None, max_waiting=2, timeout_s=1800, retention_s=3600):
        self.root = Path(
            root or os.environ.get("IFCFDS_JOB_ROOT", str(Path.cwd() / ".jobs"))
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_waiting = max_waiting
        self.timeout_s = timeout_s
        self.retention_s = retention_s
        self.repository = JobRepository()
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.closed = False
        self.thread = None

    @property
    def jobs(self):
        """Backward compatibility access to internal dict."""
        return self.repository._jobs

    def submit(self, paths, configuration, directory, mode="convert"):
        with self.lock:
            if self.repository.count_pending() >= self.max_waiting + 1:
                raise OverflowError("Job queue is full")
            jid = uuid.uuid4().hex
            job = dict(
                id=jid,
                state="QUEUED",
                directory=str(directory),
                created=time.time(),
                error=None,
                process=None,
            )
            Path(directory, "request.json").write_text(
                json.dumps(
                    dict(
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

    def cancel(self, jid):
        with self.lock:
            job = self.repository.get(jid)
            if job and job["state"] in ("QUEUED", "RUNNING"):
                job["state"] = "CANCELLED"
                job["finished"] = time.time()
                self._stop(job["process"])
                self._cleanup(job)
            return self.snapshot(jid)

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
                for jid, job in self.repository.items():
                    if (
                        job.get("finished", time.time()) + self.retention_s
                        < time.time()
                    ):
                        directory = Path(job["directory"]).resolve()
                        if directory.parent == self.root.resolve():
                            import shutil

                            shutil.rmtree(directory)
                        self.repository.delete(jid)
                running = next(
                    (j for j in self.repository.all_jobs() if j["state"] == "RUNNING"),
                    None,
                )
                if running:
                    proc = running["process"]
                    if time.time() - running["started"] > self.timeout_s:
                        self._stop(proc)
                        running.update(
                            state="TIMED_OUT",
                            error="Job deadline exceeded",
                            finished=time.time(),
                        )
                        self._cleanup(running)
                    elif proc.poll() is not None:
                        directory = Path(running["directory"])
                        if (
                            proc.returncode == 0
                            and (directory / "result.json").exists()
                        ):
                            running.update(state="COMPLETED", finished=time.time())
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
                    else:
                        pass
                else:
                    queued = next(
                        (j for j in self.repository.all_jobs() if j["state"] == "QUEUED"),
                        None,
                    )
                    if queued:
                        try:
                            # Capture stderr to error.txt if worker fails during startup
                            err_file = open(
                                Path(queued["directory"]) / "error.txt", "a", encoding="utf-8"
                            )
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
                        except OSError as exc:
                            queued.update(
                                state="FAILED", error=str(exc), finished=time.time()
                            )
                            self._cleanup(queued)
            self.wake.wait(0.1)
            self.wake.clear()


# Backward compatibility alias
JobManager = JobService
