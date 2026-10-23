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



def create_upload_store(manager, limits):
    async def store_uploads(uploads):
        max_file, max_total = limits()
        if not uploads or len(uploads) > 16:
            raise HTTPException(422, "Upload between 1 and 16 IFC files")
        import uuid

        directory = manager.root / ("job-" + uuid.uuid4().hex)
        directory.mkdir()
        total = 0
        paths = []
        original_names = {}
        try:
            for index, upload in enumerate(uploads):
                if not (upload.filename or "").lower().endswith(".ifc"):
                    raise HTTPException(422, "Only .ifc uploads are accepted")
                path = directory / f"source-{index}.ifc"
                size = 0
                with path.open("wb") as output:
                    while True:
                        chunk = await upload.read(1024**2)
                        if not chunk:
                            break
                        size += len(chunk)
                        total += len(chunk)
                        if size > max_file or total > max_total:
                            raise HTTPException(
                                413, "IFC upload exceeds configured size limit"
                            )
                        output.write(chunk)
                if size == 0:
                    raise HTTPException(422, "Empty IFC file")
                paths.append(path)
                original_names[path.name] = Path(upload.filename.replace("\\", "/")).name
            (directory / "upload-names.json").write_text(
                json.dumps(original_names), encoding="utf-8"
            )
            return directory, paths
        except (Exception, asyncio.CancelledError):
            shutil.rmtree(directory, ignore_errors=True)
            raise
        finally:
            for upload in uploads:
                await upload.close()

    return store_uploads
