"""Game-neutral event-system configuration contract."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field


DEFAULT_EVENT_CONFIG = {
    "enabled": True,
    "profile": "default",
    "async_observer_interval_ms": 250,
    "hooks": {"instances": []},
    "events": {},
}


@dataclass
class EventSystemConfig:
    enabled: bool = True
    profile: str = "default"
    async_observer_interval_ms: int = 250
    events: dict = field(default_factory=dict)
    hooks: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def default(cls) -> "EventSystemConfig":
        return cls.from_dict(copy.deepcopy(DEFAULT_EVENT_CONFIG))

    @classmethod
    def from_dict(cls, data: dict | None) -> "EventSystemConfig":
        raw_data = data if isinstance(data, dict) else {}
        merged = _deep_merge(copy.deepcopy(DEFAULT_EVENT_CONFIG), raw_data)
        return cls(
            enabled=bool(merged.get("enabled", True)),
            profile=str(merged.get("profile", "default")),
            async_observer_interval_ms=max(
                0,
                int(merged.get("async_observer_interval_ms", 250) or 0),
            ),
            events=merged.get("events", {}),
            hooks=merged.get("hooks", {}),
            raw=merged,
        )

    def event(self, event_type: str) -> dict:
        return self.events.get(event_type, {})

    def to_dict(self) -> dict:
        data = copy.deepcopy(self.raw)
        data["enabled"] = self.enabled
        data["profile"] = self.profile
        data["async_observer_interval_ms"] = int(self.async_observer_interval_ms)
        data["events"] = copy.deepcopy(self.events)
        data["hooks"] = copy.deepcopy(self.hooks)
        return data


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base
