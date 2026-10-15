"""FastAPI Local Server for Verified IFC-to-FDS Workbench Integration.

Provides high-performance local endpoints for inventory inspection,
spatial scoping, authoritative geometry conversion, and audit reporting.
"""

import os
import tempfile
from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ifc_to_fds.core.inventory import extract_inventory
from ifc_to_fds.geometry.engine import process_model_geometry
from ifc_to_fds.mapping.exporter import serialize_fds
from ifc_to_fds.mapping.scope import SpatialScope, apply_spatial_scope
from ifc_to_fds.mep.mep_graph import extract_mep_graph
from ifc_to_fds.validation.engine import run_independent_validation

app = FastAPI(
    title="Verified IFC-to-FDS Service",
    version="0.2.0",
    description="Local authoritative backend for IFC-to-FDS conversion and audit.",
)

# Enable CORS for browser workbench running from file:// or localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "ifc_to_fds", "version": "0.2.0"}


@app.post("/api/inventory")
async def api_inventory(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "model.ifc")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        model, _ = extract_inventory(tmp_path)
        if file.filename:
            model.source.filename = file.filename
        counts = {}
        for el in model.elements:
            counts[el.ifc_type] = counts.get(el.ifc_type, 0) + 1

        return {
            "filename": model.source.filename,
            "schema": model.source.schema_version,
            "sha256": model.source.file_hash_sha256,
            "total_elements": len(model.elements),
            "storeys": model.storeys,
            "type_counts": counts,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/api/convert")
async def api_convert(
    file: UploadFile = File(...),
    cell_size: float = Form(0.2),
    storey: Optional[str] = Form(None),
    all_geom: bool = Form(True),
    include_review: bool = Form(False),
):
    suffix = os.path.splitext(file.filename or "model.ifc")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        model, ifc_file = extract_inventory(tmp_path)
        if file.filename:
            model.source.filename = file.filename
        model = extract_mep_graph(model, ifc_file)

        if storey:
            scope = SpatialScope(storeys=[storey])
            model = apply_spatial_scope(model, scope)

        model = process_model_geometry(model, ifc_file)
        fds_text, manifest = serialize_fds(
            model,
            cell_size=cell_size,
            force_all_geom=all_geom,
            include_review_solids=include_review,
        )
        report = run_independent_validation(model, fds_text)

        return JSONResponse(
            content={
                "status": report.status.value,
                "fds_text": fds_text,
                "manifest": manifest.model_dump(),
                "report": report.model_dump(),
                "markdown_report": report.to_markdown(),
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# Mount repository root as static files for seamless web serving
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.isdir(repo_root):
    app.mount("/", StaticFiles(directory=repo_root, html=True), name="static")
