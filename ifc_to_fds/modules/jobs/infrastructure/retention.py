"""Filesystem retention policy, called while the job service lock is held."""

from pathlib import Path
from typing import Optional
import shutil


class FilesystemJobRetention:
    def cleanup_orphaned_directories(
        self, service, max_age_s: Optional[int] = None
    ) -> None:
        """Removes orphaned job-* directories on disk that are not registered in the database."""
        max_age = max_age_s if max_age_s is not None else service.retention_s
        now = service.clock()
        known_dirs = {
            Path(j["directory"]).resolve()
            for j in service.repository.all_jobs()
            if j.get("directory")
        }
        try:
            for entry in service.root.glob("job-*"):
                if entry.is_dir():
                    resolved = entry.resolve()
                    if resolved.parent != service.root.resolve():
                        # Never follow a job-* symlink/junction out of the owned
                        # root while cleaning orphaned directories.
                        continue
                    if resolved not in known_dirs:
                        shutil.rmtree(resolved, ignore_errors=True)
                    elif max_age > 0:
                        job_entry = next(
                            (
                                j
                                for j in service.repository.all_jobs()
                                if Path(j.get("directory", "")).resolve() == resolved
                            ),
                            None,
                        )
                        finished = job_entry.get("finished") if job_entry else None
                        last_active = (
                            max(finished or now, job_entry.get("last_accessed") or 0)
                            if job_entry
                            else now
                        )
                        if (
                            job_entry
                            and not job_entry.get("durable")
                            and finished is not None
                            and last_active + max_age < now
                        ):
                            shutil.rmtree(resolved, ignore_errors=True)
                            service.repository.delete(job_entry["id"])
        except OSError:
            pass

    def sweep(self, service, now):
        # 1. Retention sweep for non-durable jobs
        for jid, job in service.repository.items():
            if job.get("durable"):
                continue
            if service.retention_s > 0:
                last_active = max(
                    job.get("finished") or now, job.get("last_accessed") or 0
                )
                if last_active + service.retention_s < now:
                    directory = Path(job["directory"]).resolve()
                    if directory.parent == service.root.resolve():
                        shutil.rmtree(directory, ignore_errors=True)
                    service.repository.delete(jid)
