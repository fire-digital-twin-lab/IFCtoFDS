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

    @router.post("/api/preview-jobs", status_code=202)
    async def submit_preview(file: UploadFile = File(...)):
        if not manager.can_accept():
            raise HTTPException(429, "Job queue is full; retry after existing jobs finish")
        directory, paths = await store_uploads([file])
        try:
            return manager.submit(paths, {}, directory, mode="preview")
        except OverflowError as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise HTTPException(429, str(exc))


    return router
