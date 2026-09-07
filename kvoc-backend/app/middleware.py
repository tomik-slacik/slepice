"""Cross-cutting HTTP middleware - request correlation/logging and a
general rate limit, as opposed to auth.py's login-specific lockout. See
each class's docstring for what it does and, importantly, what it doesn't
(both are in-memory/per-process - config.py explains why that's an
acceptable trade-off for this project's actual deployment shape, and what
would need to change for a multi-instance one).
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import config
from .logging_setup import request_id_ctx

logger = logging.getLogger("kvoc")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Tags every request with an id - reused from an incoming X-Request-Id
    header if a client/proxy already supplied one, otherwise a fresh one -
    and makes it available to *every* log line for the duration of that
    request (see logging_setup.request_id_ctx: any module's plain
    `logging.getLogger("kvoc")` call picks it up automatically). Echoes the
    id back in the response header, and logs one line per request (method,
    path, status, how long it took) - the exception handler in main.py
    already logs failures with a traceback; this covers the other, much
    larger share of requests that just... happen, which a real deployment
    still needs a trail of to answer "what did this account actually do"
    or "was the API slow at 14:02 or was that just one client".
    """

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_ctx.set(req_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            logger.info("%s %s -> EXC after %sms", request.method, request.url.path, duration_ms)
            raise
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info("%s %s -> %s (%sms)", request.method, request.url.path, response.status_code, duration_ms)
        response.headers["X-Request-Id"] = req_id
        request_id_ctx.reset(token)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """A blunt, across-the-board per-IP sliding-window limit - next to
    auth.py's narrow, specific login lockout, this is the general backstop
    against one client hammering the API. Off by default
    (KVOC_RATE_LIMIT_PER_MINUTE unset or 0, see config.py): turning it on
    unconditionally risked 429s nobody asked for on a quiet local dev
    server, or worse, on the test suite itself, which legitimately fires
    far more than any reasonable per-minute budget in a few seconds.

    Same honesty as the login lockout: in-memory, per-process, resets on
    restart, and not shared across multiple instances of this app running
    behind a load balancer - see config.py's LOGIN_MAX_ATTEMPTS docstring
    for the same caveat spelled out in full. Also, like that dict, this one
    never prunes an IP's entry once its window has fully drained (a
    long-lived process serving many distinct IPs slowly accumulates empty
    deques) - a real concern only at a scale this project isn't at yet;
    moving both to something shared (Redis, etc.) for a multi-instance
    deployment would fix this the same time it fixes the sharing problem.
    """

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        limit = config.RATE_LIMIT_PER_MINUTE
        if not limit:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._hits[client_ip]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            return JSONResponse(status_code=429, content={"detail": "too many requests - slow down"})
        window.append(now)
        return await call_next(request)
