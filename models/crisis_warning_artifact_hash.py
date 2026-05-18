"""Stable hashing helpers for crisis warning artifact files."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ARTIFACT_HASH_ALGORITHM = "sha256"
ARTIFACT_HASH_FILENAMES = (
    "xgb_crisis_model.json",
    "calibration.json",
    "feature_schema.json",
    "shap_background_sample.csv",
)
_ARTIFACT_HASH_FILE_ORDER = {
    filename: index for index, filename in enumerate(ARTIFACT_HASH_FILENAMES)
}
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_hash_files(directory: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for filename in ARTIFACT_HASH_FILENAMES:
        path = directory / filename
        if path.exists():
            files.append(
                {
                    "path": filename,
                    "status": "present",
                    "sha256": sha256_file(path),
                }
            )
        else:
            files.append(
                {
                    "path": filename,
                    "status": "missing",
                    "sha256": None,
                }
            )
    return files


def normalize_artifact_hash_files(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("artifact_hash_files must be a list")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("artifact_hash_files entries must be objects")
        path = str(item.get("path") or "").strip()
        status = str(item.get("status") or "").strip()
        if path not in _ARTIFACT_HASH_FILE_ORDER:
            raise ValueError(f"artifact_hash_files contains an unexpected file: {path}")
        if path in seen:
            raise ValueError(f"artifact_hash_files contains a duplicate file: {path}")
        if status not in {"present", "missing"}:
            raise ValueError(f"artifact_hash_files has invalid status for {path}")

        sha_value = item.get("sha256")
        if status == "present":
            sha_text = str(sha_value or "").strip()
            if _SHA256_PATTERN.fullmatch(sha_text) is None:
                raise ValueError(f"artifact_hash_files has invalid sha256 for {path}")
            sha_value = sha_text
        else:
            sha_value = None

        normalized.append(
            {
                "path": path,
                "status": status,
                "sha256": sha_value,
            }
        )
        seen.add(path)

    missing = [filename for filename in ARTIFACT_HASH_FILENAMES if filename not in seen]
    if missing:
        raise ValueError(f"artifact_hash_files is missing entries: {missing}")

    return sorted(normalized, key=lambda item: _ARTIFACT_HASH_FILE_ORDER[item["path"]])


def artifact_hash_from_files(files: list[dict[str, Any]]) -> str:
    normalized = normalize_artifact_hash_files(files)
    payload = {
        "algorithm": ARTIFACT_HASH_ALGORITHM,
        "files": normalized,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compute_artifact_hash(directory: Path) -> tuple[str, list[dict[str, Any]]]:
    files = artifact_hash_files(directory)
    return artifact_hash_from_files(files), files
