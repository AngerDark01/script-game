"""Canonical executable definitions for configured action events."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from core.events.action_tracks import ActionTrack, TrackMode
from core.events.event_catalog import EventRecord, catalog_summary
from core.events.event_store import EventStore


@dataclass(frozen=True)
class ExecutableEventDefinition:
    """Validated execution snapshot detached from its persisted record."""

    event_id: str
    name: str
    owner_device_id: str
    revision: int
    tracks: tuple[ActionTrack, ...]
    steps: tuple[dict, ...]
    max_runs: int | None = None
    loop: bool = False
    end_ms: int | None = None


def parse_event_definition(record: Mapping) -> ExecutableEventDefinition:
    """Convert one catalog record into the sole executable representation."""

    name = str(record.get("name") or "").strip()
    if not name:
        raise ValueError("event name is required")

    tracks = tuple(_parse_track(item) for item in record.get("tracks", ()))
    steps = tuple(deepcopy(item) for item in record.get("steps", ()))
    max_runs = record.get("max_runs")
    end_ms = record.get("end_ms")
    if max_runs is not None:
        max_runs = int(max_runs)
    if end_ms is not None:
        end_ms = int(end_ms)

    return ExecutableEventDefinition(
        event_id=str(record.get("id") or ""),
        name=name,
        owner_device_id=str(record.get("owner_device_id") or ""),
        revision=int(record.get("revision") or 0),
        tracks=tracks,
        steps=steps,
        max_runs=max_runs,
        loop=bool(record.get("loop", False)),
        end_ms=end_ms,
    )


def _parse_track(record: Mapping) -> ActionTrack:
    mode = TrackMode(record.get("mode", TrackMode.ONCE.value))
    return ActionTrack(
        tuple(record.get("buttons", ())),
        mode=mode,
        hold_ms=int(record.get("hold_ms", 100)),
        interval_ms=(
            record.get("interval_ms") if mode is not TrackMode.ONCE else None
        ),
        end_ms=record.get("end_ms") if mode is not TrackMode.ONCE else None,
    )


class EventDefinitionRepository:
    """One persistence and parsing boundary for local and shared events."""

    def __init__(self, root: Path, device_id: str = "local") -> None:
        self.root = Path(root)
        self.device_id = str(device_id or "local")
        self._store = EventStore(self.root, self.device_id)

    def set_device_id(self, device_id: str) -> None:
        normalized = str(device_id or "local")
        if normalized == self.device_id:
            return
        self.device_id = normalized
        self._store = EventStore(self.root, self.device_id)

    def local_records(self) -> list[dict]:
        return self._store.local()

    def remote_records(self) -> list[dict]:
        return self._store.remote()

    def visible_records(self) -> list[dict]:
        return self._store.all_visible()

    def definitions(self) -> dict[str, ExecutableEventDefinition]:
        definitions: dict[str, ExecutableEventDefinition] = {}
        for record in self.visible_records():
            definition = parse_event_definition(record)
            if not definition.event_id:
                raise ValueError(f"event id is required: {definition.name}")
            definitions[definition.event_id] = definition
        return definitions

    def save_local(self, records: Iterable[Mapping]) -> list[dict]:
        current = {
            str(record.get("id")): EventRecord.from_dict(
                record,
                default_owner=self.device_id,
            )
            for record in self.local_records()
            if record.get("id")
        }
        saved: list[dict] = []
        for draft in records:
            value = deepcopy(dict(draft))
            event_id = str(value.get("id") or "")
            previous = current.get(event_id)
            candidate = EventRecord.from_dict(value, default_owner=self.device_id)
            if previous is None:
                record = candidate
            elif candidate.definition == previous.definition and not previous.deleted:
                record = previous
            else:
                record = previous.updated(candidate.definition)
            saved.append(record.to_dict())
        self._store.save_local(saved)
        return saved

    def apply_remote(self, records: Iterable[Mapping]) -> int:
        return self._store.apply_remote(
            [deepcopy(dict(record)) for record in records]
        )

    def by_id(self, event_id: str) -> dict | None:
        return self._store.by_id(str(event_id))

    def by_name(self, name: str) -> dict | None:
        return self._store.by_name(str(name))

    def local_by_name(self, name: str) -> dict | None:
        normalized = str(name)
        return next(
            (record for record in self.local_records() if record.get("name") == normalized),
            None,
        )

    def local_key(self, name: str) -> str | None:
        record = self.local_by_name(name)
        return str(record.get("id")) if record and record.get("id") else None

    def catalog_payload(self) -> dict:
        records = self.local_records()
        return {
            **catalog_summary(records, self.device_id),
            "definitions": records,
        }

    def resolve_shared_key(self, item: Mapping) -> str | None:
        name = str(item.get("name") or "")
        event_id = str(item.get("eventId") or "")
        if not event_id:
            fallback = self.by_name(name)
            return str(fallback.get("id")) if fallback and fallback.get("id") else None

        record = self.by_id(event_id)
        if record is not None:
            return str(record.get("id"))

        fallback = self.by_name(name)
        sent_revision = int(item.get("eventRevision") or 0)
        if fallback is not None and int(fallback.get("revision") or 0) >= sent_revision:
            return str(fallback.get("id")) if fallback.get("id") else None
        return None
