"""Request safety controls for API entrypoints."""

from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque
from typing import Awaitable, Callable, Deque, Dict, Tuple

from fastapi import Request
from starlette.responses import JSONResponse, Response

from backend.error_handling import REQUEST_ID_HEADER, request_id_from_request


DEFAULT_MAX_BODY_BYTES = 1_000_000
DEFAULT_MAX_CONCURRENT_REQUESTS = 8
DEFAULT_RATE_LIMIT_PER_MINUTE = 60
EXEMPT_PATHS = {"/", "/health"}


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)

    def allow(self, key: Tuple[str, str], limit: int, now: float) -> bool:
        if limit <= 0:
            return True
        window_start = now - 60.0
        events = self._events[key]
        while events and events[0] < window_start:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        return True

    def reset(self) -> None:
        self._events.clear()


_rate_limiter = SlidingWindowRateLimiter()
_semaphore_lock = asyncio.Lock()
_semaphore_limit = 0
_semaphore: asyncio.BoundedSemaphore | None = None


def reset_request_limiters() -> None:
    global _semaphore
    global _semaphore_limit
    _rate_limiter.reset()
    _semaphore = None
    _semaphore_limit = 0


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(0, value)


def _client_key(request: Request) -> Tuple[str, str]:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded_for:
        client = forwarded_for
    elif request.client is not None:
        client = request.client.host
    else:
        client = "unknown"
    return client, request.url.path


async def _current_semaphore(limit: int) -> asyncio.BoundedSemaphore:
    global _semaphore
    global _semaphore_limit
    async with _semaphore_lock:
        if _semaphore is None or _semaphore_limit != limit:
            _semaphore = asyncio.BoundedSemaphore(limit)
            _semaphore_limit = limit
        return _semaphore


def _error_response(status_code: int, detail: str, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "request_id": request_id},
        headers={REQUEST_ID_HEADER: request_id},
    )


async def request_controls_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)

    request_id = request_id_from_request(request)
    max_body_bytes = _positive_int_env("DFQ_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES)
    content_length = request.headers.get("content-length")
    if content_length and max_body_bytes > 0:
        try:
            body_size = int(content_length)
        except ValueError:
            body_size = 0
        if body_size > max_body_bytes:
            return _error_response(413, "Request body is too large.", request_id)

    rate_limit = _positive_int_env("DFQ_RATE_LIMIT_PER_MINUTE", DEFAULT_RATE_LIMIT_PER_MINUTE)
    if not _rate_limiter.allow(_client_key(request), rate_limit, time.monotonic()):
        return _error_response(429, "Too many requests. Please retry shortly.", request_id)

    max_concurrent = _positive_int_env(
        "DFQ_MAX_CONCURRENT_REQUESTS",
        DEFAULT_MAX_CONCURRENT_REQUESTS,
    )
    if max_concurrent <= 0:
        return await call_next(request)

    semaphore = await _current_semaphore(max_concurrent)
    if getattr(semaphore, "_value", 0) <= 0:
        return _error_response(503, "Server concurrency limit reached. Please retry shortly.", request_id)

    await semaphore.acquire()
    try:
        return await call_next(request)
    finally:
        semaphore.release()
