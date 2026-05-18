"""Shared API error response helpers."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"
INTERNAL_ERROR_DETAIL = "Internal server error. Reference request_id for support."


def request_id_from_request(request: Request) -> str:
    request_id = getattr(request.state, "request_id", "")
    if request_id:
        return str(request_id)
    inbound = request.headers.get(REQUEST_ID_HEADER, "").strip()
    request_id = inbound or uuid4().hex
    request.state.request_id = request_id
    return request_id


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = (
        getattr(request.state, "request_id", "")
        or request.headers.get(REQUEST_ID_HEADER, "").strip()
        or uuid4().hex
    )
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


def install_error_handlers(app: FastAPI, logger: logging.Logger) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = request_id_from_request(request)
        headers = dict(exc.headers or {})
        headers[REQUEST_ID_HEADER] = request_id
        detail: Any = INTERNAL_ERROR_DETAIL if exc.status_code == 500 else exc.detail
        if exc.status_code >= 500:
            logger.error(
                "http exception request_id=%s status_code=%s detail=%s",
                request_id,
                exc.status_code,
                exc.detail,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail, "request_id": request_id},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = request_id_from_request(request)
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(exc.errors()), "request_id": request_id},
            headers={REQUEST_ID_HEADER: request_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request_id_from_request(request)
        logger.exception("unhandled exception request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={"detail": INTERNAL_ERROR_DETAIL, "request_id": request_id},
            headers={REQUEST_ID_HEADER: request_id},
        )
