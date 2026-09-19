"""Logging helpers for the PoE2 live-terrain feature boundary."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from auto_modules.paths import data_root


LOGGER_NAME = "auto_modules.poe2_live_terrain"
LOG_PATH_ENV = "AUTO_MODULES_POE2_TERRAIN_LOG"


def terrain_log_path() -> Path:
    configured = os.environ.get(LOG_PATH_ENV, "").strip()
    return (
        Path(configured).expanduser().resolve()
        if configured
        else data_root() / "logs" / "poe2_live_terrain.log"
    )


def get_terrain_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    path = terrain_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
