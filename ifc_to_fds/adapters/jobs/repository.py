"""Job metadata repository backed by SQLite with in-memory caching."""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .result_contract import validate_job_result
from .evidence_index import verify_evidence_index

logger = logging.getLogger(__name__)


class JobPersistenceError(RuntimeError):
    """A queued job could not be registered durably in SQLite."""


class JobRepository:
    """Thread-safe persistent storage for job state tracking using SQLite."""

    def __init__(self, root: Optional[Path | str] = None):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._db_path: Optional[Path] = Path(root) / "jobs.sqlite3" if root else None
        if self._db_path:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
            self._load_from_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not self._db_path:
            raise RuntimeError("Database not initialized")
        conn = sqlite3.connect(str(self._db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        if not self._db_path:
            return
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    directory TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'convert',
                    created REAL NOT NULL,
                    started REAL,
                    finished REAL,
                    last_accessed REAL,
                    error TEXT,
                    retention_s REAL,
                    durable INTEGER NOT NULL DEFAULT 0,
                    peak_rss_bytes INTEGER
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created);")

    def _load_from_db(self) -> None:
        if not self._db_path:
            return
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created ASC").fetchall()
            for row in rows:
                jid = row["id"]
                self._jobs[jid] = dict(
                    id=jid,
                    state=row["state"],
                    directory=row["directory"],
                    mode=row["mode"],
                    created=row["created"],
                    started=row["started"],
                    finished=row["finished"],
                    last_accessed=row["last_accessed"],
                    error=row["error"],
                    retention_s=row["retention_s"],
                    durable=bool(row["durable"]),
                    peak_rss_bytes=row["peak_rss_bytes"],
                    process=None,
                )

    def _persist_job(
        self, jid: str, job: Dict[str, Any], *, require_durable: bool = False
    ) -> None:
        if not self._db_path:
            return
        for attempt in range(4):
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        INSERT INTO jobs (id, state, directory, mode, created, started, finished, last_accessed, error, retention_s, durable, peak_rss_bytes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            state=excluded.state,
                            directory=excluded.directory,
                            mode=excluded.mode,
                            started=excluded.started,
                            finished=excluded.finished,
                            last_accessed=excluded.last_accessed,
                            error=excluded.error,
                            retention_s=excluded.retention_s,
                            durable=excluded.durable,
                            peak_rss_bytes=excluded.peak_rss_bytes
                        WHERE ? = 0;
                    """, (
                        jid,
                        job.get("state", "QUEUED"),
                        str(job.get("directory", "")),
                        job.get("mode", "convert"),
                        float(job.get("created", 0.0)),
                        job.get("started"),
                        job.get("finished"),
                        job.get("last_accessed"),
                        job.get("error"),
                        job.get("retention_s"),
                        1 if job.get("durable") else 0,
                        job.get("peak_rss_bytes"),
                        1 if require_durable else 0,
                    ))
                    if require_durable and cursor.rowcount != 1:
                        raise JobPersistenceError(
                            "Job ID is already registered in SQLite"
                        )
                return
            except sqlite3.OperationalError as exc:
                if ("locked" in str(exc).lower() or "busy" in str(exc).lower()) and attempt < 3:
                    time.sleep(0.05 * (2 ** attempt))
                    continue
                logger.error("Failed to persist job %s to SQLite: %s", jid, exc, exc_info=True)
                if require_durable:
                    raise JobPersistenceError("Could not persist queued job metadata") from exc
                return
            except sqlite3.Error as exc:
                logger.error("Failed to persist job %s to SQLite: %s", jid, exc, exc_info=True)
                if require_durable:
                    raise JobPersistenceError("Could not persist queued job metadata") from exc
                return

    def get(self, jid: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(jid)

    def set(self, jid: str, job: Dict[str, Any]) -> None:
        self._jobs[jid] = job
        self._persist_job(jid, job)

    def register(self, jid: str, job: Dict[str, Any]) -> None:
        """Publish a new job only after its SQLite insert has committed.

        Unlike historical best-effort status updates, admission must not report
        success for work that will disappear from the queue after a restart.
        A failed registration leaves no in-memory job and cannot start a worker.
        """
        if jid in self._jobs:
            raise ValueError("Job ID is already registered")
        self._persist_job(jid, job, require_durable=True)
        self._jobs[jid] = job

    def set_durable(self, jid: str, job: Dict[str, Any]) -> None:
        """Update an existing job only after SQLite confirms the transition.

        This is deliberately distinct from historical best-effort set().
        Failure must not publish the new state to the in-memory cache.
        """
        if not self._db_path:
            self._jobs[jid] = job
            return
        for attempt in range(4):
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """UPDATE jobs SET state = ?, started = ?, finished = ?,
                           last_accessed = ?, error = ?, retention_s = ?,
                           durable = ?, peak_rss_bytes = ? WHERE id = ?""",
                        (
                            job.get("state", "QUEUED"),
                            job.get("started"),
                            job.get("finished"),
                            job.get("last_accessed"),
                            job.get("error"),
                            job.get("retention_s"),
                            1 if job.get("durable") else 0,
                            job.get("peak_rss_bytes"),
                            jid,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise JobPersistenceError(
                            "Could not update missing job metadata"
                        )
                self._jobs[jid] = job
                return
            except sqlite3.OperationalError as exc:
                if ("locked" in str(exc).lower() or "busy" in str(exc).lower()) and attempt < 3:
                    time.sleep(0.05 * (2 ** attempt))
                    continue
                logger.error(
                    "Failed to update job %s durably: %s", jid, exc, exc_info=True
                )
                raise JobPersistenceError("Could not update job metadata") from exc
            except sqlite3.Error as exc:
                logger.error(
                    "Failed to update job %s durably: %s", jid, exc, exc_info=True
                )
                raise JobPersistenceError("Could not update job metadata") from exc

    def delete(self, jid: str) -> None:
        """Remove memory state only after SQLite has committed deletion.

        Failure must not claim deletion or permit artifact cleanup while the
        durable record still points to the job directory.
        """
        if not self._db_path:
            self._jobs.pop(jid, None)
            return
        for attempt in range(4):
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM jobs WHERE id = ?", (jid,))
                self._jobs.pop(jid, None)
                return
            except sqlite3.OperationalError as exc:
                if ("locked" in str(exc).lower() or "busy" in str(exc).lower()) and attempt < 3:
                    time.sleep(0.05 * (2 ** attempt))
                    continue
                logger.error("Failed to delete job %s from SQLite: %s", jid, exc, exc_info=True)
                raise JobPersistenceError("Could not delete job metadata") from exc
            except sqlite3.Error as exc:
                logger.error("Failed to delete job %s from SQLite: %s", jid, exc, exc_info=True)
                raise JobPersistenceError("Could not delete job metadata") from exc

    def all_jobs(self) -> List[Dict[str, Any]]:
        return list(self._jobs.values())

    def items(self):
        return list(self._jobs.items())

    def contains(self, jid: str) -> bool:
        return jid in self._jobs

    def count_pending(self) -> int:
        return sum(j["state"] in ("QUEUED", "RUNNING") for j in self._jobs.values())

    def snapshot(self, jid: str) -> Dict[str, Any]:
        if jid not in self._jobs:
            raise KeyError(jid)
        job = self._jobs[jid]
        snapshot = {
            k: v
            for k, v in job.items()
            if k not in ("process", "directory") and not k.startswith("_")
        }
        directory = Path(job["directory"])
        try:
            snapshot["progress"] = json.loads(
                (directory / "progress.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            pass
        if (directory / "diagnostics.json").is_file():
            snapshot["diagnostics_url"] = f"/api/jobs/{jid}/diagnostics"
        return snapshot

    def read_result(self, jid: str, *, job: Dict[str, Any] | None = None) -> Dict[str, Any]:
        # JobService supplies a snapshot so file hashing can run without
        # blocking the job scheduler lock. Direct repository users still work.
        if job is None:
            job = self._jobs[jid]
        if job["state"] != "COMPLETED":
            raise ValueError("Job has no completed result")
        try:
            result = json.loads(
                Path(job["directory"], "result.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise ValueError("Completed job has an unreadable result.json") from exc
        mode = job.get("mode", "convert")
        validate_job_result(mode, result)
        verify_evidence_index(Path(job["directory"]), mode, result)
        # Only add URLs for whitelisted job artifacts. Do not trust URLs or
        # arbitrary filenames stored in the worker's JSON result.
        for name, artifact in result.get("artifacts", {}).items():
            if job.get("mode") in ("convert", "scenario", "preview"):
                artifact["url"] = f"/api/jobs/{jid}/artifacts/{name}"
        return result
