"""Generic message envelopes shared by communication adapters."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from .contracts import DeliveryMode, PeerId, SessionId, Topic


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class MessageEnvelope:
    """Immutable, transport-independent message metadata and payload."""

    message_id: str
    topic: Topic | str
    payload: Mapping[str, Any]
    delivery: DeliveryMode
    created_at_ms: int
    ttl_ms: int | None = None
    deadline_ms: int | None = None
    sequence: int | None = None
    sender: PeerId | None = None
    session_id: SessionId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.message_id, str) or not self.message_id.strip():
            raise ValueError("message id must be a non-empty string")
        if len(self.message_id) > 128:
            raise ValueError("message id is too long")
        object.__setattr__(self, "topic", Topic(self.topic))
        object.__setattr__(self, "delivery", DeliveryMode(self.delivery))
        if not isinstance(self.payload, Mapping):
            raise ValueError("payload must be a mapping")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        _integer(self.created_at_ms, "created_at_ms")
        if self.ttl_ms is not None:
            _integer(self.ttl_ms, "ttl_ms", minimum=1)
        if self.deadline_ms is not None:
            _integer(self.deadline_ms, "deadline_ms", minimum=1)
            if self.deadline_ms <= self.created_at_ms:
                raise ValueError("deadline_ms must be after created_at_ms")
        if self.sequence is not None:
            _integer(self.sequence, "sequence")
        if self.ttl_ms is not None and self.deadline_ms is not None:
            if self.deadline_ms > self.created_at_ms + self.ttl_ms:
                raise ValueError("deadline_ms cannot exceed ttl expiry")

    @property
    def expires_at_ms(self) -> int | None:
        expiries = []
        if self.ttl_ms is not None:
            expiries.append(self.created_at_ms + self.ttl_ms)
        if self.deadline_ms is not None:
            expiries.append(self.deadline_ms)
        return min(expiries) if expiries else None

    def is_expired(self, now_ms: int) -> bool:
        _integer(now_ms, "now_ms")
        expires_at = self.expires_at_ms
        return expires_at is not None and now_ms >= expires_at

    def remaining_ms(self, now_ms: int) -> int | None:
        _integer(now_ms, "now_ms")
        expires_at = self.expires_at_ms
        return None if expires_at is None else max(0, expires_at - now_ms)

    @classmethod
    def from_shared_position(
        cls,
        position: object,
        *,
        now_ms: int,
        message_id: str | None = None,
    ) -> "MessageEnvelope":
        """Adapt the established SharedPosition-shaped object without importing it."""

        captured_at_ms = _integer(getattr(position, "captured_at_ms"), "captured_at_ms")
        _integer(now_ms, "now_ms")
        return cls(
            message_id=message_id or uuid4().hex,
            topic=Topic.POSITION,
            payload={
                "deviceId": getattr(position, "device_id"),
                "actorId": getattr(position, "actor_id"),
                "mapId": getattr(position, "map_id"),
                "mapVersion": getattr(position, "map_version"),
                "position": list(getattr(position, "position")),
                "confidence": getattr(position, "confidence"),
                "sessionId": getattr(position, "session_id", ""),
            },
            delivery=DeliveryMode.LATEST,
            created_at_ms=captured_at_ms,
            ttl_ms=500,
        )

    @classmethod
    def from_shared_event(
        cls,
        event: object,
        *,
        now_ms: int,
        message_id: str | None = None,
    ) -> "MessageEnvelope":
        """Adapt the established SharedEvent-shaped object without importing it."""

        _integer(now_ms, "now_ms")
        deadline_ms = _integer(getattr(event, "deadline_ms"), "deadline_ms", minimum=1)
        return cls(
            message_id=message_id or uuid4().hex,
            topic=Topic.EVENT,
            payload={
                "deviceId": getattr(event, "device_id"),
                "eventId": getattr(event, "event_id"),
                "name": getattr(event, "name"),
                "targets": list(getattr(event, "targets")),
                "sessionId": getattr(event, "session_id", ""),
            },
            delivery=DeliveryMode.RELIABLE_ORDERED,
            created_at_ms=now_ms,
            deadline_ms=deadline_ms,
        )

