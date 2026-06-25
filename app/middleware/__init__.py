"""HTTP middleware components."""
from __future__ import annotations

import time
import uuid
from typing import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

_logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attaches a request_id, logs request/response, measures latency."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id

        # Bind request_id into structlog's contextvars for this request.
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        client_host = request.client.host if request.client else "-"
        _logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            client=client_host,
        )
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            _logger.exception("http.error", elapsed_ms=round(elapsed, 2))
            structlog.contextvars.clear_contextvars()
            raise

        elapsed = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = request_id
        _logger.info(
            "http.response",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=round(elapsed, 2),
        )
        structlog.contextvars.clear_contextvars()
        return response
