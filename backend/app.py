"""Lightweight ASGI entrypoint for hosted deployments."""

from __future__ import annotations

import importlib
import logging
import os
import threading
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


logger = logging.getLogger(__name__)
_backend_app: Optional[ASGIApp] = None
_backend_lock = threading.Lock()


def _configured_origins() -> list[str]:
    origins_env = os.getenv("ALLOW_ORIGINS")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


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
        try:
            backend_app = _load_backend_app()
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
    version="3.6.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health probe endpoint that does not import analytics dependencies."""
    return {"status": "ok"}


app.mount("/", LazyBackendApp())
