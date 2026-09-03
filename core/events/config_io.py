from __future__ import annotations

import json
from pathlib import Path

from .config_model import EventSystemConfig


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
