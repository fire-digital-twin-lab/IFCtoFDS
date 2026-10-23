"""Host, API key and origin guards shared by HTTP app instances."""
import hmac
import os
from fastapi import Request

async def security_guard(request: Request, call_next):
    # 1. Host header validation
    allowed_hosts_str = os.getenv("IFCFDS_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver")
    if allowed_hosts_str != "*":
        allowed_hosts = {h.strip().lower() for h in allowed_hosts_str.split(",") if h.strip()}
        host_header = request.headers.get("host", "").strip()
        if not host_header:
            raw_host = ""
        elif host_header.startswith("[") and "]" in host_header:
            raw_host = host_header[: host_header.index("]") + 1].lower()
        else:
            raw_host = host_header.split(":")[0].strip().lower()
        if not raw_host or raw_host not in allowed_hosts:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={"detail": f"Invalid Host header: {raw_host or 'missing'}"})

    # 2. API Key authentication for /api/* (excluding /api/health)
    api_key = os.getenv("IFCFDS_API_KEY")
    if api_key and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        provided_key = request.headers.get("x-api-key")
        if not provided_key:
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                provided_key = auth_header[7:].strip()
        if not provided_key or not hmac.compare_digest(provided_key, api_key):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 3. Origin guard for state-modifying requests
    origin = request.headers.get("origin")
    allowed_origins_str = os.getenv("IFCFDS_ALLOWED_ORIGINS", "")
    allowed_origins = {o.strip().rstrip("/") for o in allowed_origins_str.split(",") if o.strip()}
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and origin
        and origin.rstrip("/") != str(request.base_url).rstrip("/")
        and origin.rstrip("/") not in allowed_origins
    ):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=403,
            content={"detail": "Use the workbench served by this local backend"},
        )

    return await call_next(request)

