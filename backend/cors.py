"""CORS configuration helpers for API entrypoints."""

import os
from typing import Optional


DEFAULT_ALLOW_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
DEFAULT_ALLOW_ORIGIN_REGEX = r"https://([a-z0-9-]+\.)*(vercel\.app|hf\.space)"
HOSTED_ENVIRONMENT_MARKERS = (
    "VERCEL",
    "SPACE_ID",
    "HF_SPACE_ID",
    "K_SERVICE",
    "RENDER",
    "RAILWAY_ENVIRONMENT",
    "FLY_APP_NAME",
)


def hosted_environment_detected() -> bool:
    return any(os.getenv(marker) for marker in HOSTED_ENVIRONMENT_MARKERS)


def configured_origins() -> list[str]:
    origins_env = os.getenv("ALLOW_ORIGINS")
    if origins_env:
        return [
            origin.strip().rstrip("/")
            for origin in origins_env.split(",")
            if origin.strip()
        ]
    if hosted_environment_detected():
        raise RuntimeError("ALLOW_ORIGINS must be configured in hosted environments")
    return list(DEFAULT_ALLOW_ORIGINS)


def configured_origin_regex() -> Optional[str]:
    regex_env = os.getenv("ALLOW_ORIGIN_REGEX")
    if regex_env is not None:
        regex = regex_env.strip()
        return regex or None
    if os.getenv("ALLOW_ORIGINS"):
        return None
    if hosted_environment_detected():
        return None
    return DEFAULT_ALLOW_ORIGIN_REGEX
