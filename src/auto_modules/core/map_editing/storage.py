from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import numpy as np

from .models import WallOverrideDocument


OVERRIDE_FILENAME = "wall_overrides.npz"
OVERRIDE_CONFIG_KEY = "wall_overrides"
FORMAT_VERSION = 1


def load_wall_overrides(map_folder: str | Path, shape: tuple[int, int]) -> WallOverrideDocument:
    """Load one map's manual masks or return an empty document for legacy maps."""
    folder = Path(map_folder)
    config = _load_config(folder)
    metadata = config.get(OVERRIDE_CONFIG_KEY)
    if metadata is None:
        return WallOverrideDocument.empty(shape)
    if not isinstance(metadata, dict):
        raise ValueError("wall override metadata must be an object")
    if not metadata.get("enabled", False):
        return WallOverrideDocument.empty(shape)
    filename = str(metadata.get("file", OVERRIDE_FILENAME))
    if Path(filename).name != filename:
        raise ValueError("wall override file must be stored in the map folder")
    override_path = folder / filename
    if not override_path.is_file():
        raise ValueError(f"wall override file is missing: {override_path.name}")
    try:
        with np.load(override_path, allow_pickle=False) as data:
            if "add_mask" not in data or "erase_mask" not in data:
                raise ValueError("wall override file must contain add_mask and erase_mask")
            document = WallOverrideDocument(
                add_mask=_binary_mask(data["add_mask"]),
                erase_mask=_binary_mask(data["erase_mask"]),
            )
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"wall override file is invalid: {error}") from error
    document.validate_for(shape)
    return document


def save_wall_overrides(map_folder: str | Path, document: WallOverrideDocument) -> Path:
    """Atomically persist masks and merge only override metadata into config.json."""
    folder = Path(map_folder)
    folder.mkdir(parents=True, exist_ok=True)
    document.validate_for(tuple(document.add_mask.shape))
    override_path = folder / OVERRIDE_FILENAME
    _write_npz_atomically(
        override_path,
        add_mask=_binary_mask(document.add_mask),
        erase_mask=_binary_mask(document.erase_mask),
    )
    config = _load_config(folder)
    config[OVERRIDE_CONFIG_KEY] = {
        "enabled": True,
        "file": OVERRIDE_FILENAME,
        "format_version": FORMAT_VERSION,
    }
    _write_json_atomically(folder / "config.json", config)
    return override_path


def _load_config(folder: Path) -> dict:
    config_path = folder / "config.json"
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"map config is invalid: {error}") from error
    if not isinstance(config, dict):
        raise ValueError("map config must be an object")
    return config


def _binary_mask(mask: np.ndarray) -> np.ndarray:
    if mask.ndim != 2:
        raise ValueError("wall override masks must be two-dimensional")
    return np.where(mask > 0, 255, 0).astype(np.uint8, copy=False)


def _write_npz_atomically(path: Path, **arrays: np.ndarray) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=".npz", dir=path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        np.savez_compressed(temporary_path, **arrays)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_json_atomically(path: Path, payload: dict) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=".json", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
