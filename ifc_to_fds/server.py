"""Loopback service, bounded streaming uploads and isolated conversion jobs."""

import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import shutil
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .jobs import JobManager
from .http_limits import BodyLimitMiddleware
from .mapping.scope import SpatialScope
from .validation.acceptance import AuditConfig

manager = JobManager(
    max_waiting=int(os.getenv("IFCFDS_MAX_WAITING", "2")),
    timeout_s=float(os.getenv("IFCFDS_TIMEOUT_S", "1800")),
)
MAX_FILE = int(os.getenv("IFCFDS_MAX_FILE_BYTES", str(200 * 1024**2)))
MAX_TOTAL = int(os.getenv("IFCFDS_MAX_JOB_BYTES", str(500 * 1024**2)))


@asynccontextmanager
async def lifespan(app):
    yield
    manager.close()


app = FastAPI(
    title="IFCtoFDS local conversion and audit", version="0.3.0", lifespan=lifespan
)

app.add_middleware(BodyLimitMiddleware, maximum=MAX_TOTAL + 1024**2)


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and origin
        and origin != str(request.base_url).rstrip("/")
    ):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=403,
            content={"detail": "Use the workbench served by this local backend"},
        )
    return await call_next(request)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ifc_to_fds", "version": "0.3.0"}


def configuration_value(
    text, cell_size=None, storey=None, all_geom=None, include_review=None
):
    try:
        config = json.loads(text or "{}")
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a JSON object")
        for key, value in (
            ("cell_size", cell_size),
            ("all_geom", all_geom),
            ("include_review", include_review),
        ):
            if value is not None:
                config[key] = value
        if storey:
            config.setdefault("scope", {})["storeys"] = [storey]
        import math

        cell = float(config.get("cell_size", 0.2))
        if not math.isfinite(cell) or cell <= 0:
            raise ValueError("cell_size must be finite and positive")
        config["cell_size"] = cell
        SpatialScope.model_validate(config.get("scope", {}))
        AuditConfig.model_validate(config.get("audit", {}))
        # Executables are local operator configuration, never selectable by an upload.
        if config.get("audit", {}).get("solver_executable"):
            raise ValueError(
                "Solver executable must be configured by the local operator"
            )
        if os.getenv("IFCFDS_SOLVER"):
            config.setdefault("audit", {})["solver_executable"] = os.environ[
                "IFCFDS_SOLVER"
            ]
        from .pipeline import validate_configuration

        return validate_configuration(config)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc))


async def store_uploads(uploads):
    if not uploads or len(uploads) > 16:
        raise HTTPException(422, "Upload between 1 and 16 IFC files")
    import uuid

    directory = manager.root / ("job-" + uuid.uuid4().hex)
    directory.mkdir()
    total = 0
    paths = []
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
                    if size > MAX_FILE or total > MAX_TOTAL:
                        raise HTTPException(
                            413, "IFC upload exceeds configured size limit"
                        )
                    output.write(chunk)
            if size == 0:
                raise HTTPException(422, "Empty IFC file")
            paths.append(path)
        return directory, paths
    except Exception:
        shutil.rmtree(directory)
        raise
    finally:
        for upload in uploads:
            await upload.close()


@app.post("/api/inventory")
async def inventory(
    file: Optional[UploadFile] = File(None),
    files: Optional[list[UploadFile]] = File(None),
):
    directory, paths = await store_uploads(files or ([file] if file else []))
    try:
        job = manager.submit(paths, {}, directory, mode="inventory")
    except OverflowError as exc:
        shutil.rmtree(directory)
        raise HTTPException(429, str(exc))
    return await wait_for_job(job["id"])


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


@app.post("/api/jobs", status_code=202)
async def submit(files: list[UploadFile] = File(...), configuration: str = Form("{}")):
    config = configuration_value(configuration)
    directory, paths = await store_uploads(files)
    try:
        return manager.submit(paths, config, directory)
    except OverflowError as exc:
        shutil.rmtree(directory)
        raise HTTPException(429, str(exc))


@app.get("/api/jobs/{jid}")
def status(jid: str):
    try:
        return manager.snapshot(jid)
    except KeyError:
        raise HTTPException(404, "Unknown job")


@app.delete("/api/jobs/{jid}")
def cancel(jid: str):
    try:
        return manager.cancel(jid)
    except KeyError:
        raise HTTPException(404, "Unknown job")


@app.get("/api/jobs/{jid}/result")
def result(jid: str):
    try:
        return manager.result(jid)
    except KeyError:
        raise HTTPException(404, "Unknown job")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


ARTIFACTS = {
    "fds": "model.fds",
    "manifest": "model_manifest.json",
    "manifest_csv": "model_manifest.csv",
    "report": "model_acceptance_report.json",
    "markdown": "model_acceptance_report.md",
    "inventory": "model_inventory.json",
    "mep": "model_mep_graph.json",
    "configuration": "model_configuration.json",
}


@app.get("/api/jobs/{jid}/artifacts/{artifact}")
def artifact(jid: str, artifact: str):
    if artifact not in ARTIFACTS:
        raise HTTPException(404, "Unknown artifact")
    with manager.lock:
        if jid not in manager.jobs:
            raise HTTPException(404, "Unknown job")
        job = manager.jobs[jid]
        if job["state"] != "COMPLETED":
            raise HTTPException(409, "Job is not complete")
        path = Path(job["directory"]) / ARTIFACTS[artifact]
        if not path.exists():
            raise HTTPException(404, "Artifact not produced by this job")
        return FileResponse(path, filename=ARTIFACTS[artifact])


@app.post("/api/convert")
async def legacy_convert(
    file: UploadFile = File(...),
    cell_size: Optional[float] = Form(None),
    storey: Optional[str] = Form(None),
    all_geom: Optional[bool] = Form(None),
    include_review: Optional[bool] = Form(None),
    configuration: str = Form("{}"),
):
    config = configuration_value(
        configuration, cell_size, storey, all_geom, include_review
    )
    directory, paths = await store_uploads([file])
    try:
        job = manager.submit(paths, config, directory)
    except OverflowError as exc:
        shutil.rmtree(directory)
        raise HTTPException(429, str(exc))
    return await wait_for_job(job["id"])


# Serve only public web assets. Never expose .git, Python sources, uploads or job files.
root = Path(__file__).resolve().parent.parent
for name in ("js", "css"):
    app.mount("/" + name, StaticFiles(directory=root / name), name=name)


@app.get("/")
@app.get("/index.html")
def index():
    return FileResponse(root / "index.html")


@app.get("/guide.html")
def guide():
    return FileResponse(root / "guide.html")
