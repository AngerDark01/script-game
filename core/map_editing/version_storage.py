"""Safe persistence for complete, immutable wall-layer snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from pathlib import Path

import numpy as np

from .composition import compose_effective_wall_layer
from .storage import _load_config, _write_json_atomically, _write_npz_atomically, load_wall_overrides


VERSION_DIRNAME = "wall_versions"
VERSION_CONFIG_KEY = "wall_versions"
VERSION_FORMAT_VERSION = 1
_VERSION_ID_PATTERN = re.compile(r"v\d{4,}")


@dataclass(frozen=True)
class WallVersion:
    id: str
    file: str
    created_at: str
    parent_version: str | None


@dataclass(frozen=True)
class WallVersionCatalog:
    versions: tuple[WallVersion, ...]
    active_version: str | None
    active_wall_layer: np.ndarray


def load_wall_version_catalog(map_folder: str | Path, base_wall_layer: np.ndarray) -> WallVersionCatalog:
    """Load one active full snapshot, or use a copy of the raw map wall layer."""
    _validate_wall_layer(base_wall_layer)
    folder = Path(map_folder)
    config = _load_config(folder)
    metadata = config.get(VERSION_CONFIG_KEY)
    if metadata is None:
        return WallVersionCatalog((), None, base_wall_layer.copy())
    versions, active_version = _parse_metadata(metadata)
    active = _find_version(versions, active_version)
    return WallVersionCatalog(
        versions=versions,
        active_version=active.id,
        active_wall_layer=_load_version_wall_layer(folder, active, tuple(base_wall_layer.shape)),
    )


def save_new_wall_version(
    map_folder: str | Path,
    wall_layer: np.ndarray,
    *,
    parent_version: str | None,
) -> WallVersion:
    """Atomically create a new full snapshot and make it the active version."""
    _validate_wall_layer(wall_layer)
    folder = Path(map_folder)
    folder.mkdir(parents=True, exist_ok=True)
    config = _load_config(folder)
    existing_versions, _active = _parse_metadata(config[VERSION_CONFIG_KEY]) if VERSION_CONFIG_KEY in config else ((), None)
    if parent_version is not None:
        _find_version(existing_versions, parent_version)
    version_id = _next_version_id(existing_versions)
    filename = f"{VERSION_DIRNAME}/{version_id}.npz"
    version = WallVersion(
        id=version_id,
        file=filename,
        created_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        parent_version=parent_version,
    )
    version_path = _resolve_version_path(folder, version.file)
    version_path.parent.mkdir(parents=True, exist_ok=True)
    _write_npz_atomically(version_path, wall_layer=_binary_wall_layer(wall_layer))
    versions = (*existing_versions, version)
    config[VERSION_CONFIG_KEY] = _serialize_metadata(versions, active_version=version.id)
    _write_json_atomically(folder / "config.json", config)
    return version


def activate_wall_version(
    map_folder: str | Path,
    version_id: str,
    shape: tuple[int, int],
) -> WallVersion:
    """Validate an existing snapshot, then atomically change only the active id."""
    folder = Path(map_folder)
    config = _load_config(folder)
    if VERSION_CONFIG_KEY not in config:
        raise ValueError("wall version catalog is missing")
    versions, _active = _parse_metadata(config[VERSION_CONFIG_KEY])
    version = _find_version(versions, version_id)
    _load_version_wall_layer(folder, version, shape)
    config[VERSION_CONFIG_KEY] = _serialize_metadata(versions, active_version=version.id)
    _write_json_atomically(folder / "config.json", config)
    return version


def load_wall_version(
    map_folder: str | Path,
    version_id: str,
    shape: tuple[int, int],
) -> tuple[WallVersion, np.ndarray]:
    """Read one named immutable snapshot without changing the active pointer."""
    folder = Path(map_folder)
    config = _load_config(folder)
    if VERSION_CONFIG_KEY not in config:
        raise ValueError("wall version catalog is missing")
    versions, _active = _parse_metadata(config[VERSION_CONFIG_KEY])
    version = _find_version(versions, version_id)
    return version, _load_version_wall_layer(folder, version, shape)


def migrate_legacy_wall_overrides(map_folder: str | Path, base_wall_layer: np.ndarray) -> WallVersion | None:
    """Import an old add/erase document once without deleting its source files."""
    _validate_wall_layer(base_wall_layer)
    folder = Path(map_folder)
    config = _load_config(folder)
    if VERSION_CONFIG_KEY in config:
        return None
    legacy_metadata = config.get("wall_overrides")
    if not isinstance(legacy_metadata, dict) or not legacy_metadata.get("enabled", False):
        return None
    overrides = load_wall_overrides(folder, tuple(base_wall_layer.shape))
    effective_wall_layer = compose_effective_wall_layer(base_wall_layer, overrides)
    return save_new_wall_version(folder, effective_wall_layer, parent_version=None)


def _parse_metadata(metadata: object) -> tuple[tuple[WallVersion, ...], str]:
    if not isinstance(metadata, dict):
        raise ValueError("wall version metadata must be an object")
    if int(metadata.get("format_version", 0)) != VERSION_FORMAT_VERSION:
        raise ValueError("wall version metadata format is unsupported")
    raw_versions = metadata.get("versions")
    if not isinstance(raw_versions, list) or not raw_versions:
        raise ValueError("wall version metadata must contain versions")
    versions = tuple(_parse_version(item) for item in raw_versions)
    ids = [version.id for version in versions]
    if len(ids) != len(set(ids)):
        raise ValueError("wall version ids must be unique")
    active_version = metadata.get("active_version")
    if not isinstance(active_version, str):
        raise ValueError("wall version metadata must contain active_version")
    _find_version(versions, active_version)
    return versions, active_version


def _parse_version(raw: object) -> WallVersion:
    if not isinstance(raw, dict):
        raise ValueError("wall version entry must be an object")
    version_id = raw.get("id")
    filename = raw.get("file")
    created_at = raw.get("created_at")
    parent_version = raw.get("parent_version")
    if not isinstance(version_id, str) or not _VERSION_ID_PATTERN.fullmatch(version_id):
        raise ValueError("wall version id is invalid")
    if not isinstance(filename, str) or not isinstance(created_at, str):
        raise ValueError("wall version entry is invalid")
    if parent_version is not None and (not isinstance(parent_version, str) or not _VERSION_ID_PATTERN.fullmatch(parent_version)):
        raise ValueError("wall version parent is invalid")
    _validate_version_filename(filename, version_id)
    return WallVersion(version_id, filename, created_at, parent_version)


def _serialize_metadata(versions: tuple[WallVersion, ...], *, active_version: str) -> dict:
    return {
        "format_version": VERSION_FORMAT_VERSION,
        "active_version": active_version,
        "versions": [
            {
                "id": version.id,
                "file": version.file,
                "created_at": version.created_at,
                "parent_version": version.parent_version,
            }
            for version in versions
        ],
    }


def _find_version(versions: tuple[WallVersion, ...], version_id: str) -> WallVersion:
    for version in versions:
        if version.id == version_id:
            return version
    raise ValueError(f"wall version does not exist: {version_id}")


def _next_version_id(versions: tuple[WallVersion, ...]) -> str:
    greatest = max((int(version.id[1:]) for version in versions), default=0)
    return f"v{greatest + 1:04d}"


def _load_version_wall_layer(folder: Path, version: WallVersion, shape: tuple[int, int]) -> np.ndarray:
    path = _resolve_version_path(folder, version.file)
    if not path.is_file():
        raise ValueError(f"wall version file is missing: {version.file}")
    try:
        with np.load(path, allow_pickle=False) as data:
            if "wall_layer" not in data:
                raise ValueError("wall version file must contain wall_layer")
            wall_layer = _binary_wall_layer(data["wall_layer"])
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"wall version file is invalid: {error}") from error
    if wall_layer.shape != shape:
        raise ValueError(f"wall version shape must match base wall shape {shape}")
    return wall_layer


def _resolve_version_path(folder: Path, filename: str) -> Path:
    _validate_version_filename(filename, Path(filename).stem)
    return folder.joinpath(*Path(filename).parts)


def _validate_version_filename(filename: str, version_id: str) -> None:
    path = Path(filename)
    if path.parts != (VERSION_DIRNAME, f"{version_id}.npz"):
        raise ValueError("wall version file must be stored under wall_versions")


def _binary_wall_layer(wall_layer: np.ndarray) -> np.ndarray:
    _validate_wall_layer(wall_layer)
    return np.where(wall_layer > 0, 255, 0).astype(np.uint8, copy=False)


def _validate_wall_layer(wall_layer: np.ndarray) -> None:
    if wall_layer.ndim != 2:
        raise ValueError("wall layer must be two-dimensional")
