"""Job, preview, artifact and inventory routes; workflow logic stays in application."""
import asyncio
import json
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from ifc_to_fds.modules.artifacts.contracts import ARTIFACTS
from .configuration import configuration_value



def create_job_waiter(manager):
    async def wait_for_job(jid):
        try:
            while True:
                state = manager.snapshot(jid)
                if state["state"] == "COMPLETED":
                    return manager.result(jid)
                if state["state"] in ("FAILED", "TIMED_OUT", "CANCELLED"):
                    raise HTTPException(422, state.get("error") or state["state"])
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            manager.cancel(jid)
            raise

    return wait_for_job
