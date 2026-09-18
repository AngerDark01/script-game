"""Follow position and event transport over authenticated Host share sessions."""

from __future__ import annotations

import time
from math import isfinite
from typing import Callable

from auto_modules.adapters.virtual_gamepad.program_output import host_clock_ms
from auto_modules.core.lan_follow import SharedEvent, SharedPosition


class FollowTransport:
    """Translate generic follow contracts to and from Host protocol messages."""

    def __init__(
        self,
        client,
        *,
        clock_ms: Callable[[], int] | None = None,
        host_clock_ms_func: Callable[[], int] | None = None,
    ) -> None:
        self.client = client
        self.clock = clock_ms or (lambda: int(time.monotonic() * 1000))
        self.host_clock = host_clock_ms_func or host_clock_ms

    def publish(self, position: SharedPosition) -> bool:
        age = self.clock() - position.captured_at_ms
        if not 0 <= age < 500:
            return False
        self.client.request(
            "sync.share.position",
            {
                "actorId": position.actor_id,
                "mapId": position.map_id,
                "mapVersion": position.map_version,
                "x": position.position[0],
                "y": position.position[1],
                "confidence": position.confidence,
                "ageMs": age,
                "deadlineMs": self.host_clock() + 500 - age,
            },
        )
        return True

    def send_event(
        self,
        device_id,
        name,
        targets,
        *,
        host_deadline_ms=None,
    ):
        deadline = (
            self.host_clock() + 250
            if host_deadline_ms is None
            else host_deadline_ms
        )
        if self.host_clock() >= deadline:
            return False
        return self.client.request(
            "sync.share.event",
            {
                "deviceId": device_id,
                "name": name,
                "targets": list(targets),
                "deadlineMs": deadline,
            },
        )

    def poll(self) -> tuple[tuple[SharedPosition, ...], tuple[SharedEvent, ...]]:
        started = self.clock()
        reply = self.client.request("sync.share.drain")
        now = self.clock()
        positions: list[SharedPosition] = []
        events: list[SharedEvent] = []
        for item in reply.get("status", {}).get("sharedPositions", []):
            try:
                position = item["position"]
                age = float(item["ageMs"])
                x = float(position["x"])
                y = float(position["y"])
                confidence = float(position["confidence"])
                if (
                    not all(isfinite(value) for value in (age, x, y, confidence))
                    or not 0 <= confidence <= 1
                ):
                    continue
                captured_at_ms = int(started - age)
                if not 0 <= age < 500 or not 0 <= now - captured_at_ms < 500:
                    continue
                positions.append(
                    SharedPosition(
                        item["deviceId"],
                        position["actorId"],
                        position["mapId"],
                        position["mapVersion"],
                        (x, y),
                        confidence,
                        captured_at_ms,
                        item["sessionId"],
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        for item in reply.get("events", []):
            try:
                remaining = int(item["remainingMs"])
                deadline = started + remaining
                if not 0 < remaining <= 500 or now >= deadline:
                    continue
                events.append(
                    SharedEvent(
                        item["deviceId"],
                        item["id"],
                        item["name"],
                        tuple(item["targets"]),
                        deadline,
                        item["sessionId"],
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(positions), tuple(events)
