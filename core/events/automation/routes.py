"""Persisted event routes and pure trigger-to-dispatch decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


_LOCAL_LABELS = {"", "local", "本机", "鏈満", "b", "b端", "b绔?"}
_PAIRED_LABELS = {"paired", "remote", "已配对设备", "peer", "peers"}


def _endpoint(value, field: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _LOCAL_LABELS:
        return "local"
    if normalized in _PAIRED_LABELS:
        return "paired"
    raise ValueError(f"unknown route {field}: {value}")


def _controllers(value) -> tuple[int, ...]:
    if value is None or value == "":
        return (1,)
    if isinstance(value, (tuple, list)):
        result = tuple(dict.fromkeys(int(item) for item in value))
    else:
        text = str(value).strip().lower()
        if text in {"1", "controller 1"}:
            result = (1,)
        elif text in {"2", "controller 2"}:
            result = (2,)
        elif text in {"1+2", "1 + 2", "controller 1 + 2", "controller 1+2"}:
            result = (1, 2)
        else:
            raise ValueError(f"unknown route controller: {value}")
    if not result or any(item not in (1, 2) for item in result):
        raise ValueError(f"unknown route controller: {value}")
    return result


def _controller_label(controllers: tuple[int, ...]) -> str:
    if controllers == (1, 2):
        return "Controller 1 + 2"
    return f"Controller {controllers[0]}"


@dataclass(frozen=True)
class EventRoute:
    source: str
    trigger: str
    event_name: str
    target: str
    controllers: tuple[int, ...]

    def __post_init__(self) -> None:
        source = _endpoint(self.source, "source")
        target = _endpoint(self.target, "target")
        trigger = str(self.trigger or "").strip().upper()
        event_name = str(self.event_name or "").strip()
        controllers = _controllers(self.controllers)
        if not trigger:
            raise ValueError("route trigger is required")
        if not event_name:
            raise ValueError("route event is required")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "trigger", trigger)
        object.__setattr__(self, "event_name", event_name)
        object.__setattr__(self, "controllers", controllers)

    @classmethod
    def from_record(cls, record: Mapping) -> "EventRoute":
        return cls(
            source=record.get("source", "local"),
            trigger=record.get("trigger", ""),
            event_name=record.get("event", record.get("event_name", "")),
            target=record.get("target", "local"),
            controllers=_controllers(record.get("controller", record.get("controllers"))),
        )

    def to_record(self) -> dict:
        return {
            "source": "本机" if self.source == "local" else "已配对设备",
            "trigger": self.trigger,
            "event": self.event_name,
            "target": "本机" if self.target == "local" else "已配对设备",
            "controller": _controller_label(self.controllers),
        }


@dataclass(frozen=True)
class EventDispatch:
    event_name: str
    controllers: tuple[int, ...]
    remote: bool


class EventRouteRepository:
    def __init__(self, root: Path) -> None:
        self.path = Path(root) / "routes.json"

    def load(self) -> tuple[EventRoute, ...]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ()
        if not isinstance(raw, list):
            raise ValueError("routes.json must contain a list")
        return tuple(EventRoute.from_record(record) for record in raw)

    def save(self, routes: Iterable[EventRoute | Mapping]) -> None:
        normalized = tuple(
            route if isinstance(route, EventRoute) else EventRoute.from_record(route)
            for route in routes
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([route.to_record() for route in normalized], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class EventRouter:
    """Translate normalized trigger edges into side-effect-free dispatches."""

    def __init__(self, routes: Iterable[EventRoute]) -> None:
        self.routes = tuple(routes)

    def triggers(self, source: str = "local") -> tuple[str, ...]:
        normalized_source = _endpoint(source, "source")
        return tuple(sorted({
            route.trigger for route in self.routes if route.source == normalized_source
        }))

    def dispatches(self, trigger: str, source: str = "local") -> tuple[EventDispatch, ...]:
        normalized_trigger = str(trigger or "").strip().upper()
        normalized_source = _endpoint(source, "source")
        return tuple(
            EventDispatch(
                event_name=route.event_name,
                controllers=route.controllers,
                remote=route.target == "paired",
            )
            for route in self.routes
            if route.source == normalized_source and route.trigger == normalized_trigger
        )
