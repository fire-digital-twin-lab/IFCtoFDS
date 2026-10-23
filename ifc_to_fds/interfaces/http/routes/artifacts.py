"""Job, preview, artifact and inventory routes; workflow logic stays in application."""
import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from ifc_to_fds.modules.artifacts.contracts import ARTIFACTS
from ..configuration import configuration_value



def create_router(manager, store_uploads, wait_for_job):
    router = APIRouter()

    @router.get("/api/jobs/{jid}/artifacts/{artifact}")
    def artifact(jid: str, artifact: str):
        if artifact not in ARTIFACTS:
            raise HTTPException(404, "Unknown artifact")
        with manager.lock:
            if jid not in manager.jobs:
                raise HTTPException(404, "Unknown job")
            job = manager.jobs[jid]
            if job["state"] != "COMPLETED":
                raise HTTPException(409, "Job is not complete")
            manager.touch(jid)
            path = Path(job["directory"]) / ARTIFACTS[artifact]
            if not path.exists():
                raise HTTPException(404, "Artifact not produced by this job")
            return FileResponse(path, filename=ARTIFACTS[artifact])


    @router.get("/api/jobs/{jid}/checkpoints/{artifact}")
    def checkpoint_artifact(jid: str, artifact: str):
        if artifact not in ARTIFACTS:
            raise HTTPException(404, "Unknown artifact")
        with manager.lock:
            if jid not in manager.jobs:
                raise HTTPException(404, "Unknown job")
            job = manager.jobs[jid]
            manager.touch(jid)
            path = Path(job["directory"]) / ARTIFACTS[artifact]
            if not path.is_file():
                raise HTTPException(404, "Checkpoint artifact not available")
            response = FileResponse(path, filename=ARTIFACTS[artifact])
            response.headers["X-Verification-Status"] = (
                "UNACCEPTED-AUDIT_INCOMPLETE-DO_NOT_USE_AS_VERIFIED_OUTPUT"
            )
            return response


    @router.get("/api/jobs/{jid}/geometry-batch")
    def geometry_batch(jid: str, payloads: list[str] = Query(...)):
        if not 1 <= len(payloads) <= 16:
            raise HTTPException(422, "Request between 1 and 16 geometry payloads")
        manager.touch(jid)
        # Reuse the job-local, completed-artifact whitelist for every member.
        paths = [Path(geometry_payload(jid, key).path) for key in payloads]
        length = sum(path.stat().st_size for path in paths)
        if length > 16 * 1024**2:
            raise HTTPException(
                413, "Geometry batch exceeds 16 MiB; fetch large payloads individually"
            )

        def chunks():
            for path in paths:
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024**2), b""):
                        yield block

        return StreamingResponse(
            chunks(),
            media_type="application/octet-stream",
            headers={"Content-Length": str(length)},
        )


    @router.get("/api/jobs/{jid}/geometry/{payload}")
    def geometry_payload(jid: str, payload: str):
        if len(payload) != 64 or any(c not in "0123456789abcdef" for c in payload):
            raise HTTPException(404, "Unknown geometry payload")
        with manager.lock:
            job = manager.jobs.get(jid)
            if not job:
                raise HTTPException(404, "Unknown job")
            if job["state"] != "COMPLETED":
                raise HTTPException(409, "Job is not complete")
            manager.touch(jid)
            index_path = Path(job["directory"]) / "model_geometry.json"
            if not index_path.is_file():
                raise HTTPException(404, "Geometry index not available for this job")
            if "_geometry_payloads" not in job:
                index = json.loads(index_path.read_text(encoding="utf-8"))
                job["_geometry_payloads"] = {
                    ref["payload"]
                    for entry in index["elements"].values()
                    for ref in [entry.get("mesh"), *entry.get("openings", {}).values()]
                    if ref
                }
            linked = job["_geometry_payloads"]
            if payload not in linked:
                raise HTTPException(404, "Unlinked geometry payload")
            path = index_path.with_suffix(".payloads") / (payload + ".bin")
            if not path.is_file():
                raise HTTPException(404, "Missing geometry payload")
            return FileResponse(path, media_type="application/octet-stream")


    return router
