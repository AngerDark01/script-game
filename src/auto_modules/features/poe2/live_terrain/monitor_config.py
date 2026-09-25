"""PoE2-only monitor configuration and atomic persistence."""

from __future__ import annotations

import json
import math
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from auto_modules.core.mapping import MapStitcher
from auto_modules.core.spatial.capture_geometry import CaptureShape
from auto_modules.core.spatial.monitor_binding import (
    CaptureRect,
    MonitorBinding,
    resize_binding_around_marker,
)


def _default_stitcher_params() -> dict:
    return MapStitcher.default_params(canvas_size=5000, draw_scale=2.0)


@dataclass(frozen=True)
class Poe2MonitorConfig:
    binding: MonitorBinding | None = None
    search_radius: int = 96
    match_threshold: float = 0.72
    sample_interval_ms: int = 100
    first_frame_minimum_confidence: float = 0.70
    first_frame_anchored_score: float = 0.35
    first_frame_anchored_coverage: float = 0.45
    localization_fps: int = 30
    preview_fps: int = 12
    profile_id: str = "default"
    profile_name: str = "默认配置"
    selection_mode: str = "region"
    capture_size: int = 320
    shape: CaptureShape = CaptureShape.SQUARE
    circle_radius: float | None = None
    recognizer_params: dict = field(default_factory=dict)
    stitcher_params: dict = field(default_factory=_default_stitcher_params)

    def __post_init__(self) -> None:
        if int(self.search_radius) <= 0:
            raise ValueError("search_radius must be positive")
        if not 0.0 <= float(self.match_threshold) <= 1.0:
            raise ValueError("match_threshold must be between 0 and 1")
        if int(self.sample_interval_ms) <= 0:
            raise ValueError("sample_interval_ms must be positive")
        for name in ("first_frame_minimum_confidence", "first_frame_anchored_score"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one")
            object.__setattr__(self, name, value)
        coverage = float(self.first_frame_anchored_coverage)
        if not math.isfinite(coverage) or not 0.0 < coverage <= 1.0:
            raise ValueError("first_frame_anchored_coverage must be in (0, 1]")
        object.__setattr__(self, "first_frame_anchored_coverage", coverage)
        if not 1 <= int(self.localization_fps) <= 60:
            raise ValueError("localization_fps must be between 1 and 60")
        if not 1 <= int(self.preview_fps) <= 30 or int(self.preview_fps) > int(self.localization_fps):
            raise ValueError("preview_fps must be between 1 and 30 and no greater than localization_fps")
        object.__setattr__(self, "localization_fps", int(self.localization_fps))
        object.__setattr__(self, "preview_fps", int(self.preview_fps))
        if not str(self.profile_id).strip():
            raise ValueError("profile_id is required")
        if not str(self.profile_name).strip():
            raise ValueError("profile_name is required")
        selection_mode = str(self.selection_mode).strip().lower()
        if selection_mode not in {"region", "center"}:
            raise ValueError("selection_mode must be region or center")
        if int(self.capture_size) <= 0:
            raise ValueError("capture_size must be positive")
        shape = CaptureShape.coerce(self.shape)
        circle_radius = self.circle_radius
        if circle_radius is not None and float(circle_radius) <= 0:
            raise ValueError("circle_radius must be positive")
        object.__setattr__(self, "search_radius", int(self.search_radius))
        object.__setattr__(self, "match_threshold", float(self.match_threshold))
        object.__setattr__(self, "sample_interval_ms", int(self.sample_interval_ms))
        object.__setattr__(self, "profile_id", str(self.profile_id).strip())
        object.__setattr__(self, "profile_name", str(self.profile_name).strip())
        object.__setattr__(self, "selection_mode", selection_mode)
        object.__setattr__(self, "capture_size", int(self.capture_size))
        if selection_mode == "center" and self.binding is not None:
            object.__setattr__(
                self,
                "binding",
                resize_binding_around_marker(
                    self.binding,
                    int(self.capture_size),
                    int(self.capture_size),
                ),
            )
        object.__setattr__(self, "shape", shape)
        object.__setattr__(
            self,
            "circle_radius",
            float(circle_radius) if circle_radius is not None else None,
        )
        if not isinstance(self.recognizer_params, dict):
            raise TypeError("recognizer_params must be a dictionary")
        object.__setattr__(self, "recognizer_params", deepcopy(self.recognizer_params))
        if not isinstance(self.stitcher_params, dict):
            raise TypeError("stitcher_params must be a dictionary")
        stitcher_params = _default_stitcher_params()
        stitcher_params.update(deepcopy(self.stitcher_params))
        object.__setattr__(self, "stitcher_params", stitcher_params)

    def as_dict(self) -> dict:
        return {
            "binding": self.binding.as_dict() if self.binding is not None else None,
            "search_radius": self.search_radius,
            "match_threshold": self.match_threshold,
            "sample_interval_ms": self.sample_interval_ms,
            "first_frame_minimum_confidence": self.first_frame_minimum_confidence,
            "first_frame_anchored_score": self.first_frame_anchored_score,
            "first_frame_anchored_coverage": self.first_frame_anchored_coverage,
            "localization_fps": self.localization_fps,
            "preview_fps": self.preview_fps,
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "selection_mode": self.selection_mode,
            "capture_size": self.capture_size,
            "shape": self.shape.value,
            "circle_radius": self.circle_radius,
            "recognizer_params": deepcopy(self.recognizer_params),
            "stitcher_params": deepcopy(self.stitcher_params),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Poe2MonitorConfig":
        if not isinstance(data, dict):
            raise TypeError("monitor config payload must be a dictionary")
        return cls(
            binding=_binding_from_dict(data.get("binding")),
            search_radius=data.get("search_radius", 96),
            match_threshold=data.get("match_threshold", 0.72),
            sample_interval_ms=data.get("sample_interval_ms", 100),
            first_frame_minimum_confidence=data.get("first_frame_minimum_confidence", 0.70),
            first_frame_anchored_score=data.get("first_frame_anchored_score", 0.35),
            first_frame_anchored_coverage=data.get("first_frame_anchored_coverage", 0.45),
            localization_fps=data.get("localization_fps", 30),
            preview_fps=data.get("preview_fps", 12),
            profile_id=data.get("profile_id", "default"),
            profile_name=data.get("profile_name", "默认配置"),
            selection_mode=data.get("selection_mode", "region"),
            capture_size=data.get("capture_size", 320),
            shape=data.get("shape", CaptureShape.SQUARE.value),
            circle_radius=data.get("circle_radius"),
            recognizer_params=data.get("recognizer_params", {}),
            stitcher_params=data.get("stitcher_params", _default_stitcher_params()),
        )


class Poe2MonitorConfigStore:
    filename = "monitor.json"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.path = self.root / self.filename

    def load(self) -> Poe2MonitorConfig:
        if not self.path.is_file():
            return Poe2MonitorConfig()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return Poe2MonitorConfig()
        if not isinstance(data, dict):
            return Poe2MonitorConfig()
        try:
            return Poe2MonitorConfig.from_dict(data)
        except (TypeError, ValueError, KeyError):
            return Poe2MonitorConfig()

    def save(self, config: Poe2MonitorConfig) -> Path:
        if not isinstance(config, Poe2MonitorConfig):
            raise TypeError("config must be Poe2MonitorConfig")
        self.root.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="monitor-", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(config.as_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return self.path

    @staticmethod
    def _binding(value) -> MonitorBinding | None:
        return _binding_from_dict(value)


def _binding_from_dict(value) -> MonitorBinding | None:
    if not isinstance(value, dict):
        return None
    rect = value.get("rect")
    if not isinstance(rect, dict):
        return None
    return MonitorBinding(
        rect=CaptureRect(**rect),
        screen_id=value.get("screen_id", "primary"),
        coordinate_space=value.get("coordinate_space", "physical_desktop"),
        dpi_scale_x=value.get("dpi_scale_x", 1.0),
        dpi_scale_y=value.get("dpi_scale_y", 1.0),
        player_marker_position=(
            tuple(value["player_marker_position"])
            if value.get("player_marker_position") is not None
            else None
        ),
    )


class Poe2MonitorProfileStore:
    """Local multi-profile persistence for PoE2 monitor settings."""

    index_filename = "profiles.json"
    legacy_filename = "monitor.json"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.index_path = self.root / self.index_filename
        self.legacy_path = self.root / self.legacy_filename

    def list_profiles(self) -> tuple[Poe2MonitorConfig, ...]:
        index = self._load_index()
        profiles: list[Poe2MonitorConfig] = []
        for item in index["profiles"]:
            profile_id = str(item.get("id", "")).strip()
            if not profile_id:
                continue
            try:
                profiles.append(self.get(profile_id))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
        if profiles:
            return tuple(profiles)
        if self.legacy_path.is_file():
            config = Poe2MonitorConfigStore(self.root).load()
            self.save(config)
            return (config,)
        return ()

    def get(self, profile_id: str) -> Poe2MonitorConfig:
        profile_id = self._validate_id(profile_id)
        path = self.root / f"{profile_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return Poe2MonitorConfig.from_dict(data)

    def active(self) -> Poe2MonitorConfig | None:
        profiles = self.list_profiles()
        if not profiles:
            return None
        active_id = self._load_index().get("active_profile_id")
        for profile in profiles:
            if profile.profile_id == active_id:
                return profile
        self.activate(profiles[0].profile_id)
        return profiles[0]

    def create(self, name: str, *, template: Poe2MonitorConfig | None = None) -> Poe2MonitorConfig:
        profile_id = uuid4().hex[:12]
        config = template or Poe2MonitorConfig()
        config = Poe2MonitorConfig.from_dict(
            {**config.as_dict(), "profile_id": profile_id, "profile_name": str(name).strip() or "新配置"}
        )
        self.save(config)
        self.activate(profile_id)
        return config

    def copy(self, profile_id: str, name: str) -> Poe2MonitorConfig:
        return self.create(name, template=self.get(profile_id))

    def rename(self, profile_id: str, name: str) -> Poe2MonitorConfig:
        config = self.get(profile_id)
        renamed = Poe2MonitorConfig.from_dict(
            {**config.as_dict(), "profile_name": str(name).strip() or config.profile_name}
        )
        self.save(renamed)
        return renamed

    def activate(self, profile_id: str) -> Poe2MonitorConfig:
        config = self.get(profile_id)
        index = self._load_index()
        index["active_profile_id"] = config.profile_id
        self._write_index(index)
        return config

    def save(self, config: Poe2MonitorConfig) -> Path:
        if not isinstance(config, Poe2MonitorConfig):
            raise TypeError("config must be Poe2MonitorConfig")
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{self._validate_id(config.profile_id)}.json"
        _atomic_json_write(path, config.as_dict())
        index = self._load_index()
        entries = [item for item in index["profiles"] if item.get("id") != config.profile_id]
        entries.append({"id": config.profile_id, "name": config.profile_name})
        index["profiles"] = entries
        index.setdefault("active_profile_id", config.profile_id)
        self._write_index(index)
        return path

    def delete(self, profile_id: str) -> None:
        profile_id = self._validate_id(profile_id)
        profiles = [item for item in self.list_profiles() if item.profile_id != profile_id]
        path = self.root / f"{profile_id}.json"
        if path.exists():
            path.unlink()
        index = self._load_index()
        index["profiles"] = [{"id": item.profile_id, "name": item.profile_name} for item in profiles]
        if index.get("active_profile_id") == profile_id:
            index["active_profile_id"] = profiles[0].profile_id if profiles else None
        self._write_index(index)

    def _load_index(self) -> dict:
        if not self.index_path.is_file():
            return {"active_profile_id": None, "profiles": []}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {"active_profile_id": None, "profiles": []}
        if not isinstance(data, dict) or not isinstance(data.get("profiles", []), list):
            return {"active_profile_id": None, "profiles": []}
        return {"active_profile_id": data.get("active_profile_id"), "profiles": data["profiles"]}

    def _write_index(self, data: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        _atomic_json_write(self.index_path, data)

    @staticmethod
    def _validate_id(profile_id: str) -> str:
        value = str(profile_id).strip()
        if not value or value in {".", ".."} or any(char in value for char in "\\/\0"):
            raise ValueError("invalid profile id")
        return value


def _atomic_json_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


__all__ = ["Poe2MonitorConfig", "Poe2MonitorConfigStore", "Poe2MonitorProfileStore"]
