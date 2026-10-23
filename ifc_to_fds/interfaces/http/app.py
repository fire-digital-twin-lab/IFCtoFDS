"""HTTP composition and lifecycle; importing the app does not open a job database."""
from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from ifc_to_fds.http_limits import BodyLimitMiddleware
from ifc_to_fds.bootstrap.job_manager import LazyJobManager
from ifc_to_fds.web_assets import frontend_root
from .configuration import configuration_value
from .routes import create_router
from .security import security_guard

MAX_FILE = int(os.getenv("IFCFDS_MAX_FILE_BYTES", str(200 * 1024**2)))
MAX_TOTAL = int(os.getenv("IFCFDS_MAX_JOB_BYTES", str(500 * 1024**2)))


def create_app(job_manager=None):
    manager = job_manager if job_manager is not None else LazyJobManager()

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            manager.close()

    application = FastAPI(title="IFCtoFDS local conversion and audit", version="0.5.0", lifespan=lifespan)
    application.add_middleware(BodyLimitMiddleware, maximum=MAX_TOTAL + 1024**2)
    application.middleware("http")(security_guard)
    router = create_router(manager, lambda: (MAX_FILE, MAX_TOTAL))
    application.include_router(router)
    application.state.job_manager = manager
    application.state.router = router
    root = frontend_root()
    for name in ("src", "styles", "vendor", "generated"):
        application.mount("/" + name, StaticFiles(directory=root / name), name=name)
    application.mount("/frontend", StaticFiles(directory=root, html=True), name="frontend")

    @application.get("/")
    @application.get("/index.html")
    def index():
        return FileResponse(root / "index.html")

    @application.get("/guide.html")
    def guide():
        return FileResponse(root / "guide.html")

    return application


app = create_app()
manager = app.state.job_manager
store_uploads = app.state.router.store_uploads
