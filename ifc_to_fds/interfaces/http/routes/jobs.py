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

    @router.post("/api/inventory")
    async def inventory(
        file: Optional[UploadFile] = File(None),
        files: Optional[list[UploadFile]] = File(None),
    ):
        if not manager.can_accept():
            raise HTTPException(429, "Job queue is full; retry after existing jobs finish")
        directory, paths = await store_uploads(files or ([file] if file else []))
        try:
            job = manager.submit(paths, {}, directory, mode="inventory")
        except OverflowError as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise HTTPException(429, str(exc))
        return await wait_for_job(job["id"])


    @router.post("/api/jobs", status_code=202)
    async def submit(files: list[UploadFile] = File(...), configuration: str = Form("{}")):
        config = configuration_value(configuration)
        if not manager.can_accept():
            raise HTTPException(429, "Job queue is full; retry after existing jobs finish")
        directory, paths = await store_uploads(files)
        try:
            return manager.submit(paths, config, directory)
        except OverflowError as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise HTTPException(429, str(exc))


    @router.get("/api/jobs/{jid}")
    def status(jid: str):
        try:
            return manager.snapshot(jid)
        except KeyError:
            raise HTTPException(404, "Unknown job")


    @router.delete("/api/jobs/{jid}")
    def cancel(jid: str):
        try:
            return manager.delete_job(jid)
        except KeyError:
            raise HTTPException(404, "Unknown job")


    @router.get("/api/jobs/{jid}/result")
    def result(jid: str):
        try:
            manager.touch(jid)
            return manager.result(jid)
        except KeyError:
            raise HTTPException(404, "Unknown job")
        except ValueError as exc:
            raise HTTPException(409, str(exc))


    @router.get("/api/jobs/{jid}/diagnostics")
    def diagnostics(jid: str):
        with manager.lock:
            job = manager.jobs.get(jid)
            if not job:
                raise HTTPException(404, "Unknown job")
            manager.touch(jid)
            path = Path(job["directory"]) / "diagnostics.json"
            if not path.is_file():
                raise HTTPException(404, "No diagnostic produced")
            return FileResponse(
                path, filename="diagnostics.json", media_type="application/json"
            )


    @router.post("/api/convert")
    async def legacy_convert(
        file: UploadFile = File(...),
        cell_size: Optional[float] = Form(None),
        storey: Optional[str] = Form(None),
        all_geom: Optional[bool] = Form(None),
        include_review: Optional[bool] = Form(None),
        profile: Optional[str] = Form(None),
        configuration: str = Form("{}"),
    ):
        if not manager.can_accept():
            raise HTTPException(429, "Job queue is full; retry after existing jobs finish")
        config = configuration_value(
            configuration,
            cell_size=cell_size,
            storey=storey,
            all_geom=all_geom,
            include_review=include_review,
            profile=profile,
        )
        directory, paths = await store_uploads([file])
        try:
            job = manager.submit(paths, config, directory)
        except OverflowError as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise HTTPException(429, str(exc))
        return await wait_for_job(job["id"])


    return router
