from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_EVENT_CONFIG = {
    "enabled": True,
    "profile": "default",
    "events": {
        "portal": {
            "enabled": True,
            "priority": 100,
            "interaction": "key",
            "minimap_threshold": 0.74,
            "max_candidates": 2,
            "min_blue_ratio": 0.08,
            "stable_frames": 3,
            "localization_cluster_radius": 56,
            "stable_variance": 1600,
            "dedupe_radius": 32,
            "localization_max_samples": 12,
            "localization_cluster_ttl_ms": 12000,
            "memory_confirm_frames": 1,
            "arrival_radius": 80,
            "interact_radius": 36,
            "retry_limit": 2,
            "cooldown_ms": 120000,
            "cooldown_radius": 260,
            "exit_complete_radius": 120,
            "type_cooldown_ms": 10000,
            "portal_point_click_wait_ms": 350,
            "post_interact_wait_ms": 800,
            "teleport_timeout_ms": 6000,
            "teleport_min_distance": 180,
            "environment_change_threshold": 0.18,
        }
    },
}


@dataclass
class EventSystemConfig:
    enabled: bool = True
    profile: str = "default"
    events: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def default(cls) -> "EventSystemConfig":
        data = copy.deepcopy(DEFAULT_EVENT_CONFIG)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "EventSystemConfig":
        merged = _deep_merge(copy.deepcopy(DEFAULT_EVENT_CONFIG), data or {})
        return cls(
            enabled=bool(merged.get("enabled", True)),
            profile=str(merged.get("profile", "default")),
            events=merged.get("events", {}),
            raw=merged,
        )

    def event(self, event_type: str) -> dict:
        return self.events.get(event_type, {})

    def to_dict(self) -> dict:
        data = copy.deepcopy(self.raw)
        data["enabled"] = self.enabled
        data["profile"] = self.profile
        data["events"] = copy.deepcopy(self.events)
        return data


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def event_config_path(map_folder) -> Path:
    return Path(map_folder) / "event_config.json"


def load_event_config(map_folder) -> EventSystemConfig:
    path = event_config_path(map_folder)
    if not path.exists():
        return EventSystemConfig.default()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        data = {}
    return EventSystemConfig.from_dict(data)


def save_event_config(map_folder, config: EventSystemConfig) -> bool:
    path = event_config_path(map_folder)
    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(config.to_dict(), handle, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def build_tui_event_options(registry, config: EventSystemConfig) -> list[dict]:
    """Return complete event options for a TUI/config surface.

    This intentionally exposes only EventDefinition-level events such as
    "portal", never internal detectors or confirmers.
    """
    options = []
    for definition in registry.definitions():
        current = config.event(definition.event_type)
        options.append(
            {
                "event_type": definition.event_type,
                "display_name": definition.display_name,
                "description": getattr(definition, "description", ""),
                "enabled": bool(current.get("enabled", True)),
                "schema": definition.config_schema(),
                "current_values": current,
            }
        )
    return options
