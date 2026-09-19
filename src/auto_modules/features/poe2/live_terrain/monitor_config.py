"""PoE2-only monitor configuration and atomic persistence."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from auto_modules.core.spatial.monitor_binding import CaptureRect, MonitorBinding


@dataclass(frozen=True)
class Poe2MonitorConfig:
    binding: MonitorBinding | None = None
    search_radius: int = 96
    match_threshold: float = 0.72
    sample_interval_ms: int = 100

    def __post_init__(self) -> None:
        if int(self.search_radius) <= 0:
            raise ValueError("search_radius must be positive")
        if not 0.0 <= float(self.match_threshold) <= 1.0:
            raise ValueError("match_threshold must be between 0 and 1")
        if int(self.sample_interval_ms) <= 0:
            raise ValueError("sample_interval_ms must be positive")
        object.__setattr__(self, "search_radius", int(self.search_radius))
        object.__setattr__(self, "match_threshold", float(self.match_threshold))
        object.__setattr__(self, "sample_interval_ms", int(self.sample_interval_ms))

    def as_dict(self) -> dict:
        return {
            "binding": self.binding.as_dict() if self.binding is not None else None,
            "search_radius": self.search_radius,
            "match_threshold": self.match_threshold,
            "sample_interval_ms": self.sample_interval_ms,
        }


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
            binding = self._binding(data.get("binding"))
            return Poe2MonitorConfig(
                binding=binding,
                search_radius=data.get("search_radius", 96),
                match_threshold=data.get("match_threshold", 0.72),
                sample_interval_ms=data.get("sample_interval_ms", 100),
            )
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


__all__ = ["Poe2MonitorConfig", "Poe2MonitorConfigStore"]
