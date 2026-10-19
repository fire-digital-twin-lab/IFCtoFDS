"""Job metadata repository backed by SQLite with in-memory caching."""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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

    def _persist_job(self, jid: str, job: Dict[str, Any]) -> None:
        if not self._db_path:
            return
        for attempt in range(4):
            try:
                with self._get_connection() as conn:
                    conn.execute("""
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
                            peak_rss_bytes=excluded.peak_rss_bytes;
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
                    ))
                return
            except sqlite3.OperationalError as exc:
                if ("locked" in str(exc).lower() or "busy" in str(exc).lower()) and attempt < 3:
                    time.sleep(0.05 * (2 ** attempt))
                    continue
                logger.error("Failed to persist job %s to SQLite: %s", jid, exc, exc_info=True)
                return
            except sqlite3.Error as exc:
                logger.error("Failed to persist job %s to SQLite: %s", jid, exc, exc_info=True)
                return

    def get(self, jid: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(jid)

    def set(self, jid: str, job: Dict[str, Any]) -> None:
        self._jobs[jid] = job
        self._persist_job(jid, job)

    def delete(self, jid: str) -> None:
        self._jobs.pop(jid, None)
        if self._db_path:
            for attempt in range(4):
                try:
                    with self._get_connection() as conn:
                        conn.execute("DELETE FROM jobs WHERE id = ?", (jid,))
                    return
                except sqlite3.OperationalError as exc:
                    if ("locked" in str(exc).lower() or "busy" in str(exc).lower()) and attempt < 3:
                        time.sleep(0.05 * (2 ** attempt))
                        continue
                    logger.error("Failed to delete job %s from SQLite: %s", jid, exc, exc_info=True)
                    return
                except sqlite3.Error as exc:
                    logger.error("Failed to delete job %s from SQLite: %s", jid, exc, exc_info=True)
                    return

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

    def read_result(self, jid: str) -> Dict[str, Any]:
        job = self._jobs[jid]
        if job["state"] != "COMPLETED":
            raise ValueError("Job has no completed result")
        result = json.loads(
            Path(job["directory"], "result.json").read_text(encoding="utf-8")
        )
        for name, artifact in result.get("artifacts", {}).items():
            artifact["url"] = f"/api/jobs/{jid}/artifacts/{name}"
        return result
