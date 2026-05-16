"""Lightweight ASGI entrypoint for hosted deployments."""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import threading
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.cors import configured_origin_regex, configured_origins


logger = logging.getLogger(__name__)
_backend_app: Optional[ASGIApp] = None
_backend_lock = threading.Lock()


def _backend_startup_timeout_seconds() -> float:
    try:
        value = float(os.getenv("DFQ_BACKEND_STARTUP_TIMEOUT_SECONDS", "60"))
    except ValueError:
        return 60.0
    return max(1.0, value)


def _load_backend_app() -> ASGIApp:
    global _backend_app
    if _backend_app is not None:
        return _backend_app
    with _backend_lock:
        if _backend_app is None:
            module = importlib.import_module("backend.main")
            _backend_app = module.app
    return _backend_app


class LazyBackendApp:
    """Load the full analytics API only when an analytics route is requested."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http" and scope.get("path") in {"/", "/health"}:
            response = JSONResponse({"status": "ok"})
            await response(scope, receive, send)
            return

        try:
            backend_app = await asyncio.wait_for(
                asyncio.to_thread(_load_backend_app),
                timeout=_backend_startup_timeout_seconds(),
            )
        except asyncio.TimeoutError:
            logger.exception("full backend startup timed out")
            response = JSONResponse(
                {
                    "detail": (
                        "Backend startup timed out. Please retry shortly while analytics "
                        "dependencies finish loading."
                    )
                },
                status_code=504,
            )
            await response(scope, receive, send)
            return
        except Exception as exc:
            logger.exception("full backend startup failed")
            response = JSONResponse(
                {"detail": f"Backend startup failed: {exc}"},
                status_code=500,
            )
            await response(scope, receive, send)
            return
        await backend_app(scope, receive, send)


app = FastAPI(
    title="DeepFirm Quant",
    description="Industrial-grade quant risk and decision engine",
    version="4.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins(),
    allow_origin_regex=configured_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root_health_check() -> dict[str, str]:
    """Root probe endpoint that does not import analytics dependencies."""
    return {"status": "ok"}


@app.head("/")
async def root_head_check() -> dict[str, str]:
    """Root HEAD probe endpoint that does not import analytics dependencies."""
    return {"status": "ok"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health probe endpoint that does not import analytics dependencies."""
    return {"status": "ok"}


app.mount("/", LazyBackendApp())
