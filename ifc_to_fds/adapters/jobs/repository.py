"""Job metadata repository."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class JobRepository:
    """Thread-safe storage for job state tracking."""

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def get(self, jid: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(jid)

    def set(self, jid: str, job: Dict[str, Any]) -> None:
        self._jobs[jid] = job

    def delete(self, jid: str) -> None:
        self._jobs.pop(jid, None)

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
        snapshot = {
            k: v
            for k, v in self._jobs[jid].items()
            if k not in ("process", "directory") and not k.startswith("_")
        }
        directory = Path(self._jobs[jid]["directory"])
        try:
            snapshot["progress"] = json.loads((directory / "progress.json").read_text(encoding="utf-8"))
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
