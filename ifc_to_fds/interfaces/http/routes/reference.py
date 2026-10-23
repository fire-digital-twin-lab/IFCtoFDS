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

    @router.get("/api/reference-cases")
    def reference_cases():
        from ifc_to_fds.modules.reference.api import registered_cases

        return {"cases": registered_cases()}


    return router
