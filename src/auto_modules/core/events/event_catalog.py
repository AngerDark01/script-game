"""Versioned bidirectional event catalog primitives.

The owner device is the only writer; peers keep read-only copies.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EventRecord:
    id: str
    name: str
    owner_device_id: str
    revision: int
    updated_at: str
    deleted: bool
    definition: dict
    content_hash: str

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "owner_device_id": self.owner_device_id,
            "revision": self.revision, "updated_at": self.updated_at,
            "deleted": self.deleted, "content_hash": self.content_hash,
            **deepcopy(self.definition),
        }

    @classmethod
    def from_dict(cls, data: dict, *, default_owner: str) -> "EventRecord":
        event_id = str(data.get("id") or uuid4())
        owner = str(data.get("owner_device_id") or default_owner)
        definition = {k: deepcopy(v) for k, v in data.items()
                      if k not in {"id", "name", "owner_device_id", "revision", "updated_at", "deleted", "content_hash"}}
        definition.setdefault("name", str(data.get("name", "未命名事件")))
        revision = max(1, int(data.get("revision", 1)))
        digest = str(data.get("content_hash") or _hash(definition))
        return cls(event_id, str(data.get("name") or definition.get("name") or "未命名事件"), owner,
                   revision, str(data.get("updated_at") or _now()), bool(data.get("deleted", False)), definition, digest)

    def updated(self, definition: dict) -> "EventRecord":
        if self.deleted:
            raise ValueError("deleted event cannot be updated")
        value = deepcopy(definition)
        value.setdefault("name", self.name)
        return EventRecord(self.id, str(value.get("name", self.name)), self.owner_device_id,
                           self.revision + 1, _now(), False, value, _hash(value))

    def tombstone(self) -> "EventRecord":
        return EventRecord(self.id, self.name, self.owner_device_id, self.revision + 1,
                           _now(), True, deepcopy(self.definition), self.content_hash)


def migrate_events(items: list[dict] | None, owner_device_id: str) -> list[dict]:
    """Migrate legacy name-only events while preserving their track definitions."""
    return [EventRecord.from_dict(item, default_owner=owner_device_id).to_dict()
            for item in (items or []) if isinstance(item, dict)]


def catalog_summary(items: list[dict], device_id: str) -> dict:
    records = [EventRecord.from_dict(item, default_owner=device_id) for item in items]
    rows = [{"id": r.id, "name": r.name, "ownerDeviceId": r.owner_device_id,
             "revision": r.revision, "updatedAt": r.updated_at,
             "deleted": r.deleted, "contentHash": r.content_hash} for r in records]
    return {"deviceId": device_id, "catalogRevision": max((r.revision for r in records), default=0),
            "catalogHash": _hash({"events": rows}), "events": rows}
