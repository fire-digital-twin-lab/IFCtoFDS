"""Bound the HTTP body before multipart parsing/spooling."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, maximum):
        self.app = app
        self.maximum = maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid content length"}, 400)(
                scope, receive, send
            )
        if length > self.maximum or length < 0:
            return await JSONResponse({"detail": "Request exceeds upload limit"}, 413)(
                scope, receive, send
            )
        consumed = 0
        response_started = False

        async def wrapped_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > self.maximum:
                raise HTTPException(413, "Request exceeds upload limit")
            return message

        try:
            return await self.app(scope, bounded_receive, wrapped_send)
        except HTTPException as exc:
            if not response_started:
                response = JSONResponse(
                    {"detail": exc.detail},
                    status_code=exc.status_code,
                )
                return await response(scope, receive, send)
            raise
