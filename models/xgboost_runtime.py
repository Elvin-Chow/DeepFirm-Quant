"""Runtime compatibility helpers for XGBoost."""

from __future__ import annotations

import importlib
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path
from types import ModuleType


def _site_package_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("purelib", "platlib"):
        value = sysconfig.get_paths().get(key)
        if value:
            roots.append(Path(value))
    roots.extend(Path(entry) for entry in sys.path if "site-packages" in entry)
    clean: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen and resolved.exists():
            seen.add(resolved)
            clean.append(resolved)
    return clean


def _openmp_candidates() -> list[Path]:
    candidates: list[Path] = []
    for root in _site_package_roots():
        candidates.extend(
            [
                root / "sklearn" / ".dylibs" / "libomp.dylib",
                root / "torch" / "lib" / "libomp.dylib",
            ]
        )
    candidates.extend(
        [
            Path("/opt/homebrew/opt/libomp/lib/libomp.dylib"),
            Path("/usr/local/opt/libomp/lib/libomp.dylib"),
            Path("/opt/local/lib/libomp/libomp.dylib"),
        ]
    )
    return [path for path in candidates if path.exists()]


def _xgboost_library_candidates() -> list[Path]:
    return [
        root / "xgboost" / "lib" / "libxgboost.dylib"
        for root in _site_package_roots()
        if (root / "xgboost" / "lib" / "libxgboost.dylib").exists()
    ]


def _purge_partial_xgboost_import() -> None:
    for name in list(sys.modules):
        if name == "xgboost" or name.startswith("xgboost."):
            sys.modules.pop(name, None)


def _patch_macos_openmp_dependency() -> None:
    libomp_candidates = _openmp_candidates()
    xgboost_candidates = _xgboost_library_candidates()
    if not libomp_candidates:
        raise RuntimeError("libomp.dylib was not found in the current Python environment")
    if not xgboost_candidates:
        raise RuntimeError("libxgboost.dylib was not found in the current Python environment")

    libomp_path = libomp_candidates[0]
    for xgboost_path in xgboost_candidates:
        dependencies = subprocess.run(
            ["otool", "-L", str(xgboost_path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if "@rpath/libomp.dylib" not in dependencies:
            continue
        subprocess.run(
            [
                "install_name_tool",
                "-change",
                "@rpath/libomp.dylib",
                str(libomp_path),
                str(xgboost_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )


def import_xgboost() -> ModuleType:
    """Import XGBoost and repair the local macOS OpenMP link when needed."""
    try:
        return importlib.import_module("xgboost")
    except Exception as first_error:
        if platform.system() != "Darwin" or "libomp" not in str(first_error):
            raise

        _purge_partial_xgboost_import()
        try:
            _patch_macos_openmp_dependency()
        except Exception as repair_error:
            raise RuntimeError(
                "xgboost could not load because libomp.dylib is unavailable, "
                "and automatic OpenMP repair failed"
            ) from repair_error

        _purge_partial_xgboost_import()
        try:
            return importlib.import_module("xgboost")
        except Exception as second_error:
            raise RuntimeError("xgboost import failed after automatic OpenMP repair") from second_error
