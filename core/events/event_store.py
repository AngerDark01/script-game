"""Local editable and remote read-only event catalogs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .event_catalog import EventRecord, migrate_events


class EventStore:
    def __init__(self, root: Path, device_id: str):
        self.root = Path(root)
        self.device_id = device_id
        self.local_path = self.root / "events.json"
        self.remote_path = self.root / "remote_events.json"

    def _read(self, path: Path) -> list[dict]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, ValueError):
            return []

    def local(self) -> list[dict]:
        records = migrate_events(self._read(self.local_path), self.device_id)
        return [item for item in records if not item.get("deleted", False)]

    def remote(self) -> list[dict]:
        return [item for item in self._read(self.remote_path) if not item.get("deleted", False)]

    def all_visible(self) -> list[dict]:
        return self.local() + self.remote()

    def save_local(self, items: Iterable[dict]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        migrated = migrate_events(list(items), self.device_id)
        self.local_path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8")

    def apply_remote(self, items: Iterable[dict]) -> int:
        incoming = [EventRecord.from_dict(item, default_owner="remote").to_dict() for item in items]
        current = {item.get("id"): item for item in self._read(self.remote_path) if item.get("id")}
        applied = 0
        for item in incoming:
            event_id = item["id"]
            old = current.get(event_id)
            if old is not None and int(old.get("revision", 0)) >= int(item.get("revision", 0)):
                continue
            current[event_id] = item
            applied += 1
        self.root.mkdir(parents=True, exist_ok=True)
        self.remote_path.write_text(json.dumps(list(current.values()), ensure_ascii=False, indent=2), encoding="utf-8")
        return applied

    def by_id(self, event_id: str) -> dict | None:
        return next((item for item in self.all_visible() if item.get("id") == event_id), None)

    def by_name(self, name: str) -> dict | None:
        return next((item for item in self.all_visible() if item.get("name") == name), None)
