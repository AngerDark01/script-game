"""Follow position and event transport over authenticated Host share sessions."""

from __future__ import annotations

import time
from math import isfinite
from typing import Callable

from auto_modules.adapters.virtual_gamepad.program_output import host_clock_ms
from auto_modules.core.communication import Capability, DeliveryMode, MessageEnvelope, PeerId, Topic
from auto_modules.core.lan_follow import SharedEvent, SharedPosition


class FollowTransport:
    """Translate generic follow contracts to and from Host protocol messages."""

    def __init__(
        self,
        client,
        *,
        manager=None,
        peer_id: str | None = None,
        clock_ms: Callable[[], int] | None = None,
        host_clock_ms_func: Callable[[], int] | None = None,
    ) -> None:
        self.client = client
        self.manager = manager
        self.peer_id = str(peer_id or "")
        self._leases = {}
        self.clock = clock_ms or (lambda: int(time.monotonic() * 1000))
        self.host_clock = host_clock_ms_func or host_clock_ms

    def publish(self, position: SharedPosition) -> bool:
        age = self.clock() - position.captured_at_ms
        if not 0 <= age < 500:
            return False
        if self.manager is not None:
            created = self.host_clock()
            self._lease(Capability.POSITION_PUBLISH).publish(
                MessageEnvelope(
                    message_id=f"position-{position.actor_id}-{position.captured_at_ms}",
                    topic=Topic.POSITION,
                    payload={
                        "actorId": position.actor_id,
                        "mapId": position.map_id,
                        "mapVersion": position.map_version,
                        "x": position.position[0],
                        "y": position.position[1],
                        "confidence": position.confidence,
                        "ageMs": age,
                    },
                    delivery=DeliveryMode.LATEST,
                    created_at_ms=created,
                    deadline_ms=created + 500 - age,
                )
            )
            return True
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
        if self.manager is not None:
            created = self.host_clock()
            self._lease(Capability.EVENT_PUBLISH).publish(
                MessageEnvelope(
                    message_id=f"event-{self.host_clock()}-{name}",
                    topic=Topic.EVENT,
                    payload={
                        "deviceId": str(device_id),
                        "name": name,
                        "targets": list(targets),
                    },
                    delivery=DeliveryMode.RELIABLE_ORDERED,
                    created_at_ms=created,
                    deadline_ms=deadline,
                )
            )
            return True
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
        if self.manager is not None:
            self.manager.pump()
            communication = getattr(getattr(self.manager, "transport", None), "adapter", None)
            if communication is None:
                return (), ()
            return self._poll_pending(communication.pop(Topic.POSITION), communication.pop(Topic.EVENT))
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

    def _poll_pending(self, position_items, event_items):
        started = self.clock()
        positions: list[SharedPosition] = []
        events: list[SharedEvent] = []
        for item in position_items:
            try:
                position = item["position"]
                positions.append(
                    SharedPosition(
                        str(item["deviceId"]),
                        str(position["actorId"]),
                        str(position["mapId"]),
                        str(position["mapVersion"]),
                        (float(position["x"]), float(position["y"])),
                        float(position["confidence"]),
                        int(started - int(item.get("ageMs", 0))),
                        str(item.get("sessionId", "")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        for item in event_items:
            try:
                remaining = int(item.get("remainingMs", 500))
                if remaining <= 0:
                    continue
                events.append(
                    SharedEvent(
                        str(item["deviceId"]),
                        str(item.get("id") or item.get("eventId") or ""),
                        str(item["name"]),
                        tuple(str(target) for target in item["targets"]),
                        started + remaining,
                        str(item.get("sessionId", "")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(positions), tuple(events)

    def _lease(self, capability: Capability):
        key = (self.peer_id, capability)
        lease = self._leases.get(key)
        if lease is None or lease.closed:
            if self.manager is None or not self.peer_id:
                raise RuntimeError("manager mode requires a peer_id")
            lease = self.manager.acquire(PeerId(self.peer_id), capability)
            self._leases[key] = lease
        return lease

    def close(self) -> None:
        for lease in tuple(self._leases.values()):
            lease.close()
        self._leases.clear()
