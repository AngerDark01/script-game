"""Stable paths for source checkouts and installed Auto Modules payloads."""

from __future__ import annotations

import os
from pathlib import Path


_PACKAGE_ROOT = Path(__file__).resolve().parent


def package_root() -> Path:
    """Return the installed ``auto_modules`` package directory."""
    return _PACKAGE_ROOT


def repository_root() -> Path:
    """Return the source repository or installed ``app`` directory."""
    for candidate in (_PACKAGE_ROOT, *_PACKAGE_ROOT.parents):
        if (candidate / "main.py").is_file() and (
            candidate / "src" / "auto_modules"
        ).is_dir():
            return candidate
    # A normal wheel/editable install has ``.../src/auto_modules`` even when a
    # launcher is not present. Keep that layout deterministic for tooling.
    return _PACKAGE_ROOT.parents[1]


def resource_root() -> Path:
    """Return the immutable resource directory."""
    configured = os.environ.get("AUTO_MODULES_RESOURCE_DIR")
    return Path(configured).resolve() if configured else repository_root() / "resources"


def data_root() -> Path:
    """Return the writable application-data directory."""
    configured = os.environ.get("AUTO_MODULES_DATA_DIR")
    return Path(configured).resolve() if configured else repository_root() / "data"
