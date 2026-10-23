"""Compose route groups while preserving the original router factory."""
from fastapi import APIRouter
from ..uploads import create_upload_store
from ..waiting import create_job_waiter
from . import reference, health, jobs, previews, artifacts


def create_router(manager, limits):
    router = APIRouter()
    store_uploads = create_upload_store(manager, limits)
    wait_for_job = create_job_waiter(manager)
    for group in (reference, health, jobs, previews, artifacts):
        # These groups have no prefix, dependencies or lifecycle of their own.
        # Preserve the flat route surface exposed by the historical factory.
        router.routes.extend(group.create_router(manager, store_uploads, wait_for_job).routes)
    router.store_uploads = store_uploads
    return router
